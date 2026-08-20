"""Messages, and the three verdicts a send can have.

THE VERDICT RULE, which is the whole reason this module exists separately:
`ACCEPTED` means a relay took responsibility for every recipient. It does NOT
mean the mail was delivered, and nothing here will ever claim it did — delivery
is decided later, by a server we do not run, and is reported (if at all) by a
bounce arriving minutes or hours afterwards.

`UNKNOWN` is a real, distinct third state, not a tidier spelling of failure. A
connection that drops after the message data was handed over may well have
delivered it; retrying is how a recipient gets the same mail twice. Collapsing
it into either neighbour is how a send path starts reporting a number nobody
should trust.
"""
from __future__ import annotations

import mimetypes
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import formatdate, make_msgid, parseaddr

#: A relay accepted responsibility for every recipient. NOT proof of delivery.
ACCEPTED = "accepted"
#: Nothing was handed to a relay. Safe to fix and retry.
REFUSED = "refused"
#: We could not tell. Retrying may duplicate the message.
UNKNOWN = "unknown"

VERDICTS = (ACCEPTED, REFUSED, UNKNOWN)


class MailError(Exception):
    """Anything awmail refuses or cannot complete."""


class RefusedError(MailError):
    """A local rule refused before anything was sent. Nothing left this machine."""


def _as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    return [str(v).strip() for v in value if str(v).strip()]


def address_of(value: str) -> str:
    """The bare address out of `Name <a@b>`, lowercased. '' when unparseable."""
    return (parseaddr(value or "")[1] or "").strip().lower()


@dataclass
class Attachment:
    filename: str
    content: bytes
    mimetype: str = ""

    def parts(self) -> tuple[str, str]:
        guess = self.mimetype or mimetypes.guess_type(self.filename)[0] or ""
        maintype, _, subtype = guess.partition("/")
        return (maintype or "application", subtype or "octet-stream")


@dataclass
class Message:
    """One outbound message. `sender` is filled in by the Mailer if left blank."""

    to: list[str]
    subject: str = ""
    body: str = ""
    sender: str = ""
    cc: list[str] = field(default_factory=list)
    bcc: list[str] = field(default_factory=list)
    reply_to: str = ""
    html: str = ""
    attachments: list[Attachment] = field(default_factory=list)
    headers: dict[str, str] = field(default_factory=dict)
    #: Set when this message is a machine-generated reply. Suppresses the
    #: recipient's own auto-responder, which is half of loop prevention.
    auto_replied: bool = False
    #: The Message-ID this replies to, if any.
    in_reply_to: str = ""
    references: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.to = _as_list(self.to)
        self.cc = _as_list(self.cc)
        self.bcc = _as_list(self.bcc)
        self.references = _as_list(self.references)

    def recipients(self) -> list[str]:
        """Every envelope recipient, de-duplicated, order preserved."""
        seen: dict[str, None] = {}
        for addr in list(self.to) + list(self.cc) + list(self.bcc):
            key = address_of(addr)
            if key:
                seen.setdefault(key, None)
        return list(seen)

    def to_mime(self, message_id: str = "") -> EmailMessage:
        mime = EmailMessage()
        mime["From"] = self.sender
        if self.to:
            mime["To"] = ", ".join(self.to)
        if self.cc:
            mime["Cc"] = ", ".join(self.cc)
        # Bcc is deliberately NOT written as a header: it goes in the envelope
        # only. Writing it would disclose every hidden recipient to all of them.
        mime["Subject"] = self.subject
        mime["Date"] = formatdate(localtime=True)
        mime["Message-ID"] = message_id or make_msgid()
        if self.reply_to:
            mime["Reply-To"] = self.reply_to
        if self.in_reply_to:
            mime["In-Reply-To"] = self.in_reply_to
        refs = list(self.references)
        if self.in_reply_to and self.in_reply_to not in refs:
            refs.append(self.in_reply_to)
        if refs:
            mime["References"] = " ".join(refs)
        if self.auto_replied:
            # Tells the far side's vacation responder not to answer this, which
            # is the half of loop prevention that lives outside our process.
            mime["Auto-Submitted"] = "auto-replied"
        for key, value in self.headers.items():
            if key.lower() in mime:
                del mime[key]
            mime[key] = value

        mime.set_content(self.body or "")
        if self.html:
            mime.add_alternative(self.html, subtype="html")
        for att in self.attachments:
            maintype, subtype = att.parts()
            mime.add_attachment(att.content, maintype=maintype,
                                subtype=subtype, filename=att.filename)
        return mime


@dataclass
class SendResult:
    """The outcome of one send. Read `status`, never just truthiness."""

    status: str
    detail: str = ""
    accepted: list[str] = field(default_factory=list)
    rejected: dict[str, str] = field(default_factory=dict)
    message_id: str = ""

    @property
    def ok(self) -> bool:
        """True only for ACCEPTED. UNKNOWN is deliberately not ok."""
        return self.status == ACCEPTED

    def __str__(self) -> str:
        bits = [self.status]
        if self.accepted:
            bits.append("accepted=" + ",".join(self.accepted))
        if self.rejected:
            bits.append("rejected=" + ",".join(sorted(self.rejected)))
        if self.detail:
            bits.append(self.detail)
        return " ".join(bits)
