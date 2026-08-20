"""awmail -- give an agent an email address: send, and actually receive.

    from awmail import Mailer
    m = Mailer.bridge(sender="you@example.com", username="you@example.com",
                      password=BRIDGE_PASSWORD, allow=["*@example.com"])
    m.send(to="sam@example.com", subject="hello", body="from your agent")

    for msg in m.inbox(limit=5):
        print(msg.subject)
        m.reply(msg, "got it")        # refuses if replying would start a loop

Two transports behind one interface, because the setup cost is the whole
product: a local bridge on 127.0.0.1 needs no domain, no DNS records and no
provider account, and sends FROM the address you already use; plain SMTP is
there for a machine that already has a relay.

Three things this package will not do, each of which is why a naive one is worse
than none: it will not send anywhere you did not allow, it will not report a
send it did not have, and it will not answer a machine and start a loop.
"""
from awmail.client import Mailer
from awmail.guard import Limits, SendGuard, is_automated, may_auto_reply
from awmail.message import (
    ACCEPTED,
    REFUSED,
    UNKNOWN,
    VERDICTS,
    Attachment,
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
    parse_message,
)

__version__ = "0.1.0"

__all__ = [
    "Mailer",
    "Message", "Received", "Attachment", "SendResult",
    "SmtpTransport", "ImapReceiver", "parse_message",
    "SendGuard", "Limits", "is_automated", "may_auto_reply",
    "MailError", "RefusedError", "address_of",
    "ACCEPTED", "REFUSED", "UNKNOWN", "VERDICTS",
    "BRIDGE_SMTP_PORT", "BRIDGE_IMAP_PORT",
    "__version__",
]
