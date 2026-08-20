"""The one class most people touch.

    from awmail import Mailer
    m = Mailer.bridge(sender="you@example.com", username="you@example.com",
                      password=BRIDGE_PASSWORD, allow=["*@example.com"])
    m.send(to="sam@example.com", subject="hello", body="from your agent")
    for msg in m.inbox(limit=5):
        print(msg.subject)

`reply()` is the interesting one: it refuses to answer machine-generated mail,
so an agent left running against a mailbox cannot start a loop with another
agent doing the same thing.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

from awmail.guard import Limits, SendGuard, may_auto_reply
from awmail.message import (
    REFUSED,
    MailError,
    Message,
    RefusedError,
    SendResult,
    address_of,
)
from awmail.transport import (
    BRIDGE_IMAP_PORT,
    BRIDGE_SMTP_PORT,
    ImapReceiver,
    Received,
    SmtpTransport,
)

logger = logging.getLogger("awmail")


def _env_list(name: str) -> list[str]:
    raw = os.environ.get(name, "")
    return [p.strip() for p in raw.split(",") if p.strip()]


def _env_int(name: str, default: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise MailError(
            name + " must be a number, got " + repr(raw)
        ) from exc


@dataclass
class Mailer:
    """Send and receive, with the rails on.

    `allow` has no permissive default anywhere in this package. An unset
    allowlist raises with an actionable message rather than quietly permitting
    the whole internet, because an agent that can mail anyone is an
    exfiltration path and that decision should be one somebody typed.
    """

    sender: str
    transport: SmtpTransport
    receiver: ImapReceiver | None = None
    guard: SendGuard = field(default_factory=SendGuard)

    @classmethod
    def bridge(cls, sender: str, username: str, password: str,
               host: str = "127.0.0.1", smtp_port: int = BRIDGE_SMTP_PORT,
               imap_port: int = BRIDGE_IMAP_PORT, allow=None,
               limits: Limits | None = None, receive: bool = True) -> "Mailer":
        """A local mail bridge - the no-domain, no-DNS, no-provider path."""
        return cls(
            sender=sender,
            transport=SmtpTransport.bridge(username, password, host=host,
                                           port=smtp_port),
            receiver=(ImapReceiver.bridge(username, password, host=host,
                                          port=imap_port) if receive else None),
            guard=SendGuard(allow=list(allow or []),
                            limits=limits or Limits()),
        )

    @classmethod
    def smtp(cls, sender: str, host: str, port: int = 587, username: str = "",
             password: str = "", security: str = "starttls", allow=None,
             limits: Limits | None = None, imap_host: str = "",
             imap_port: int = 993) -> "Mailer":
        """Any SMTP server. Add `imap_host` to be able to receive as well."""
        receiver = None
        if imap_host:
            receiver = ImapReceiver(host=imap_host, port=imap_port,
                                    username=username, password=password,
                                    security="ssl" if imap_port == 993 else "starttls")
        return cls(
            sender=sender,
            transport=SmtpTransport(host=host, port=port, username=username,
                                    password=password, security=security),
            receiver=receiver,
            guard=SendGuard(allow=list(allow or []), limits=limits or Limits()),
        )

    @classmethod
    def from_env(cls) -> "Mailer":
        """Build from AWMAIL_* environment variables.

        AWMAIL_TRANSPORT  bridge (default) or smtp
        AWMAIL_FROM       the address mail is sent as            (required)
        AWMAIL_USER       mailbox username, defaults to AWMAIL_FROM
        AWMAIL_PASSWORD   mailbox or bridge password             (required)
        AWMAIL_ALLOW      comma-separated allowlist patterns     (required)
        AWMAIL_HOST / AWMAIL_PORT / AWMAIL_SECURITY
        AWMAIL_IMAP_HOST / AWMAIL_IMAP_PORT
        """
        kind = (os.environ.get("AWMAIL_TRANSPORT") or "bridge").strip().lower()
        sender = (os.environ.get("AWMAIL_FROM") or "").strip()
        password = os.environ.get("AWMAIL_PASSWORD") or ""
        username = (os.environ.get("AWMAIL_USER") or sender).strip()
        allow = _env_list("AWMAIL_ALLOW")
        # AWMAIL_ALLOW is required HERE, not deferred to the first send. The
        # docstring above called it required and the code did not enforce it,
        # which is the same declared-here-not-real-there shape this package
        # exists to avoid -- and a Mailer that constructs fine and refuses
        # every send looks like a broken library rather than a missing setting.
        missing = [n for n, v in (("AWMAIL_FROM", sender),
                                  ("AWMAIL_PASSWORD", password),
                                  ("AWMAIL_ALLOW", allow)) if not v]
        if missing:
            raise MailError("awmail is not configured: " + ", ".join(missing)
                            + " is unset. Run `awmail doctor` to see the whole list.")
        if kind == "bridge":
            return cls.bridge(
                sender=sender, username=username, password=password,
                host=(os.environ.get("AWMAIL_HOST") or "127.0.0.1").strip(),
                smtp_port=_env_int("AWMAIL_PORT", BRIDGE_SMTP_PORT),
                imap_port=_env_int("AWMAIL_IMAP_PORT", BRIDGE_IMAP_PORT),
                allow=allow,
            )
        if kind == "smtp":
            host = (os.environ.get("AWMAIL_HOST") or "").strip()
            if not host:
                raise MailError("AWMAIL_TRANSPORT=smtp needs AWMAIL_HOST")
            return cls.smtp(
                sender=sender, host=host, port=_env_int("AWMAIL_PORT", 587),
                username=username, password=password,
                security=(os.environ.get("AWMAIL_SECURITY") or "starttls").strip(),
                allow=allow,
                imap_host=(os.environ.get("AWMAIL_IMAP_HOST") or "").strip(),
                imap_port=_env_int("AWMAIL_IMAP_PORT", 993),
            )
        raise MailError("AWMAIL_TRANSPORT must be 'bridge' or 'smtp', got "
                        + repr(kind))

    # ---- sending ----------------------------------------------------------

    def send_message(self, msg: Message) -> SendResult:
        """Send a prepared `Message`. Raises `RefusedError` before anything leaves."""
        if not msg.sender:
            msg.sender = self.sender
        self.guard.check(msg)
        result = self.transport.send(msg)
        if result.status != REFUSED:
            # Counted whenever the message really was handed over, UNKNOWN
            # included - an unknown send consumed real quota at the relay, and
            # not counting it is how a runaway loop stays under the cap.
            self.guard.record(msg)
        return result

    def send(self, to, subject: str = "", body: str = "", **kw) -> SendResult:
        """Send one message. Extra keywords go to `Message`."""
        return self.send_message(Message(to=to, subject=subject, body=body, **kw))

    def reply(self, received: Received, body: str, subject: str = "",
              auto: bool = True, **kw) -> SendResult:
        """Reply to a received message, refusing when that would risk a loop.

        `auto=True` marks this as machine-generated, which both suppresses the
        far side's vacation responder and makes our own refusal rules apply. Pass
        `auto=False` only when a human actually wrote the reply.
        """
        if auto:
            allowed, why_not = may_auto_reply(received, self.our_addresses())
            if not allowed:
                raise RefusedError("not replying: " + why_not)
        target = received.reply_to or received.sender
        if not address_of(target):
            raise RefusedError("the message carries no usable reply address")
        subject = subject or _reply_subject(received.subject)
        refs = list(received.headers.get("references", "").split())
        if received.message_id and received.message_id not in refs:
            refs.append(received.message_id)
        return self.send_message(Message(
            to=[target], subject=subject, body=body, sender=self.sender,
            in_reply_to=received.message_id, references=refs,
            auto_replied=auto, **kw))

    def our_addresses(self) -> list[str]:
        out = [self.sender]
        if self.transport.username:
            out.append(self.transport.username)
        return [a for a in out if a]

    # ---- receiving --------------------------------------------------------

    def inbox(self, folder: str = "INBOX", limit: int = 20,
              unseen_only: bool = False, mark_seen: bool = False) -> list[Received]:
        """Read mail. Raises `MailError` when this Mailer cannot receive."""
        if self.receiver is None:
            raise MailError(
                "this Mailer has no receiver, so it can only send. Build it with "
                "Mailer.bridge(...) or pass imap_host= to Mailer.smtp(...)."
            )
        return self.receiver.fetch(folder=folder, limit=limit,
                                   unseen_only=unseen_only, mark_seen=mark_seen)

    # ---- diagnosis --------------------------------------------------------

    def doctor(self) -> dict:
        """Can this actually send and receive? Three verdicts, never a boolean.

        Each probe is "ok", "failed", or "unknown", and an unreachable server is
        never reported as a clean configuration - a check that cannot look must
        not answer as though it looked.
        """
        report: dict = {
            "sender": self.sender,
            "transport": type(self.transport).__name__,
            "host": self.transport.host,
            "port": self.transport.port,
            "allowlist": list(self.guard.allow),
            "can_receive": self.receiver is not None,
        }
        report["allowlist_configured"] = "ok" if self.guard.allow else "failed"
        try:
            server = self.transport._connect()
            try:
                if self.transport.username:
                    server.login(self.transport.username, self.transport.password)
                report["smtp"] = "ok"
            finally:
                try:
                    server.quit()
                except Exception as exc:  # noqa: BLE001 - closing is not the test
                    logger.debug("SMTP close during doctor was not clean: %s", exc)
        except MailError as exc:
            report["smtp"] = "failed"
            report["smtp_detail"] = str(exc)
        except Exception as exc:  # noqa: BLE001 - any failure to reach it counts
            report["smtp"] = "failed"
            report["smtp_detail"] = type(exc).__name__ + ": " + str(exc)

        if self.receiver is None:
            report["imap"] = "unknown"
            report["imap_detail"] = "no receiver configured (send-only)"
        else:
            try:
                self.receiver.fetch(limit=1)
                report["imap"] = "ok"
            except Exception as exc:  # noqa: BLE001
                report["imap"] = "failed"
                report["imap_detail"] = type(exc).__name__ + ": " + str(exc)
        return report


def _reply_subject(subject: str) -> str:
    subject = (subject or "").strip()
    if not subject:
        return "Re:"
    return subject if subject.lower().startswith("re:") else "Re: " + subject
