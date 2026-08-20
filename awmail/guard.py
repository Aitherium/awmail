"""The rails. An agent with a send button is a spam cannon and an exfiltration
path, so every send passes through here first.

Three properties this module exists to hold, each of which is the reason a naive
mail library is worse than no mail library:

1. NOTHING IS SENT ANYWHERE THAT WAS NOT ALLOWED. The allowlist has no permissive
   default. `Mailer(allow=["*"])` is a decision someone typed; an unset allowlist
   is a refusal with an actionable message, never a quiet "send anywhere".

2. A REFUSAL RAISES. It does not return an empty result, log a warning, or
   degrade to a no-op. A fail-closed path that always returns nothing passes
   every "did it refuse?" test while being completely inert, and that failure
   mode is invisible precisely because it looks like working software.

3. AUTO-REPLY PLUS AUTO-RECEIVE IS A MAIL LOOP, and a loop between two agents
   sends thousands of messages before a human notices. Loop detection is a floor
   requirement here, not a later hardening pass.
"""
from __future__ import annotations

import fnmatch
import time
from dataclasses import dataclass, field

from awmail.message import Message, RefusedError, address_of

#: Headers that mean "a machine generated this". Replying to any of them risks a
#: loop, and RFC 3834 asks us not to.
_AUTO_HEADERS = {
    "auto-submitted": lambda v: v.strip().lower() != "no",
    "precedence": lambda v: v.strip().lower() in {"bulk", "list", "junk", "auto_reply"},
    "x-auto-response-suppress": lambda v: bool(v.strip()),
    "list-id": lambda v: bool(v.strip()),
    "list-unsubscribe": lambda v: bool(v.strip()),
}


@dataclass
class Limits:
    """Caps. Deliberately low: a correct agent rarely needs more, and a runaway
    one is stopped in minutes rather than after a mailbox is ruined."""

    per_hour: int = 60
    per_day: int = 250
    max_recipients: int = 25
    #: How deep a reply chain may go before we assume it is a loop.
    max_thread_depth: int = 25


@dataclass
class SendGuard:
    """Allowlist + caps + loop detection. Stateful: it counts what it allowed."""

    allow: list[str] = field(default_factory=list)
    limits: Limits = field(default_factory=Limits)
    #: Monotonic timestamps of previously allowed sends, newest last.
    _sent_at: list[float] = field(default_factory=list, repr=False)

    def _now(self) -> float:
        return time.time()

    def allows_address(self, addr: str) -> bool:
        target = address_of(addr) or (addr or "").strip().lower()
        if not target:
            return False
        for pattern in self.allow:
            pat = (pattern or "").strip().lower()
            if pat and fnmatch.fnmatch(target, pat):
                return True
        return False

    def _prune(self, now: float) -> None:
        day_ago = now - 86400.0
        self._sent_at = [t for t in self._sent_at if t >= day_ago]

    def check(self, msg: Message) -> None:
        """Raise `RefusedError` if this message must not be sent. Returns None if it may.

        Called before the transport is even opened, so a refusal is provably a
        message that never left this machine.
        """
        if not self.allow:
            raise RefusedError(
                "awmail has no allowlist, so it refuses to send. This is not a bug: "
                "an agent that can mail anyone is an exfiltration path. Pass "
                "allow=['*@example.com'] to permit one domain, or allow=['*'] to "
                "permit everywhere, or set AWMAIL_ALLOW."
            )

        recipients = msg.recipients()
        if not recipients:
            raise RefusedError("no recipients")

        if len(recipients) > self.limits.max_recipients:
            raise RefusedError(
                f"{len(recipients)} recipients exceeds max_recipients="
                f"{self.limits.max_recipients}"
            )

        blocked = [r for r in recipients if not self.allows_address(r)]
        if blocked:
            raise RefusedError(
                "not on the allowlist: " + ", ".join(sorted(blocked))
                + " (allow=" + ", ".join(self.allow) + ")"
            )

        if len(msg.references) > self.limits.max_thread_depth:
            raise RefusedError(
                f"reply chain is {len(msg.references)} deep, over max_thread_depth="
                f"{self.limits.max_thread_depth} — this looks like a mail loop"
            )

        if msg.auto_replied:
            sender = address_of(msg.sender)
            if sender and sender in recipients:
                raise RefusedError(
                    "an automatic reply addressed to its own sender is a loop by "
                    "construction"
                )

        now = self._now()
        self._prune(now)
        hour_ago = now - 3600.0
        in_hour = sum(1 for t in self._sent_at if t >= hour_ago)
        if in_hour >= self.limits.per_hour:
            raise RefusedError(f"rate cap reached: {in_hour} sent in the last hour "
                          f"(per_hour={self.limits.per_hour})")
        if len(self._sent_at) >= self.limits.per_day:
            raise RefusedError(f"rate cap reached: {len(self._sent_at)} sent in the last day "
                          f"(per_day={self.limits.per_day})")

    def record(self, msg: Message) -> None:
        """Count one send against the caps. Called only after a real handoff."""
        self._sent_at.append(self._now())


def is_automated(headers) -> bool:
    """True if these inbound headers say a machine generated the message.

    Never auto-reply to one. `headers` is anything with a case-insensitive
    `.get()` — an `email.message.Message` qualifies, so does a plain dict if its
    keys are already lowercase.
    """
    for name, decides in _AUTO_HEADERS.items():
        value = None
        try:
            value = headers.get(name)
            if value is None:
                value = headers.get(name.title())
        except (AttributeError, TypeError):
            return False
        if value and decides(str(value)):
            return True
    return False


def may_auto_reply(received, our_addresses=()) -> tuple[bool, str]:
    """(may_we, why_not). The single call an agent makes before answering mail.

    Refuses when the message is machine-generated, when it came from one of our
    own addresses (the tightest possible loop), or when it has no usable
    reply address.
    """
    if is_automated(received.headers):
        return (False, "the message is machine-generated (auto-submitted, bulk or a list)")
    origin = address_of(received.reply_to or received.sender)
    if not origin:
        return (False, "no usable reply address")
    ours = {address_of(a) for a in our_addresses if address_of(a)}
    if origin in ours:
        return (False, "it came from one of our own addresses, so a reply is a loop")
    return (True, "")
