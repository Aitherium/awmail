# awmail

Give an agent an email address. Send, and actually receive.

```bash
pip install awmail
```

```python
from awmail import Mailer

m = Mailer.bridge(
    sender="you@example.com",
    username="you@example.com",
    password=BRIDGE_PASSWORD,
    allow=["*@example.com"],          # who this agent may write to
)

m.send(to="sam@example.com", subject="the report", body="attached below")

for msg in m.inbox(limit=5):
    print(msg.sender, msg.subject)
    m.reply(msg, "got it")            # refuses if replying would start a loop
```

No domain. No DNS records. No provider account. No dependencies.

## Why this exists

An agent that cannot send email cannot finish most real errands. It drafts the
invitation, the receipt, the reply — and then hands a human a block of text to
paste somewhere.

The usual fix is a transactional provider, which means buying a domain, adding
DNS records, opening an account and warming it up, all so a program can send one
message from a mailbox you already own. And receiving is worse: almost nothing
gives an agent an inbox, so agents end up write-only and cannot close a loop
that a person closes by hitting reply.

## Two ways in

**A local bridge** — Proton Bridge and its equivalents expose ordinary IMAP and
SMTP on `127.0.0.1`. Your mail goes out *from the address you already use*, with
no new infrastructure at all.

```python
Mailer.bridge(sender="you@proton.me", username="you@proton.me",
              password=BRIDGE_PASSWORD, allow=["*"])
```

**Any SMTP server** — what a server usually already has.

```python
Mailer.smtp(sender="agent@example.com", host="smtp.example.com", port=587,
            username="agent@example.com", password=PASSWORD,
            allow=["*@example.com"],
            imap_host="imap.example.com")     # add this to be able to receive
```

Or configure it from the environment and call `Mailer.from_env()`:

```bash
AWMAIL_TRANSPORT=bridge          # or smtp
AWMAIL_FROM=you@example.com
AWMAIL_PASSWORD=...
AWMAIL_ALLOW='*@example.com'     # comma-separated patterns
```

```bash
awmail doctor        # tells you exactly which pieces are missing
awmail send sam@example.com --subject "hi" --body "from your agent"
awmail inbox --limit 5
```

## Three things it will not do

These are the reason a careless mail library is worse than none.

**It will not send anywhere you did not allow.** The allowlist has no permissive
default. An unset allowlist raises with an actionable message rather than
quietly permitting the whole internet, because an agent that can mail anyone is
an exfiltration path, and that should be a decision somebody typed. There are
rate caps too, low by default: a correct agent rarely needs more, and a runaway
one is stopped in minutes instead of after a mailbox is ruined.

**It will not report a send it did not have.** There are three verdicts, not
two:

| verdict | means |
|---|---|
| `ACCEPTED` | a relay took responsibility for every recipient |
| `REFUSED` | nothing was handed over — safe to fix and retry |
| `UNKNOWN` | we could not tell — retrying may duplicate the message |

`ACCEPTED` is **not** proof of delivery, and nothing here will claim it is:
delivery is decided later, by a server nobody here runs. `UNKNOWN` is a real
third state rather than a tidier spelling of failure — a connection that drops
*after* the message data was handed over may well have delivered it, and
collapsing that into `REFUSED` is how a retry mails someone the same thing
twice.

```python
result = m.send(to="sam@example.com", subject="hi")
if result.ok:            # True only for ACCEPTED
    ...
print(result.status, result.rejected)
```

**It will not answer a machine.** Auto-reply plus auto-receive is a mail loop,
and two agents can exchange thousands of messages before anyone notices.
`reply()` refuses to answer anything carrying `Auto-Submitted`, `Precedence:
bulk`, or list headers; it refuses to answer your own addresses; it refuses a
reply chain past a depth limit; and every reply it does send is marked
`Auto-Submitted: auto-replied` so the *other* side's vacation responder stays
quiet too.

## Inbound mail is data, never instruction

An email body is written by whoever felt like writing to you — and increasingly
by someone who knows an agent will read it. `as_context()` fences and labels it
before it goes anywhere near a prompt:

```python
agent.ask("Summarise this and tell me if it needs a human:\n"
          + msg.as_context())
```

That label lives in the library rather than in each caller's prompt, because
exactly one caller will forget. It labels, it does not censor: a summariser
needs the actual text.

## Composes with

Useful alone — a mailbox and a password is the whole setup. It also fits the
rest of the family: [awnboard](https://github.com/Aitherium/awnboard) mints
addressed invitations that need delivering,
[awnest](https://github.com/Aitherium/awnest) proves a human is behind an
inbound reply, [awseal](https://github.com/Aitherium/awseal) signs what you send
so a recipient can verify it really came from your agent, and
[awdk](https://github.com/Aitherium/awdk) is the agent runtime that wants all of
the above.

## Verifying it

```bash
awmail --self-test        # offline, no server, no network
pytest                    # includes a real SMTP conversation over a real socket
```

The suite runs a tiny SMTP server on a socket and sends to it through real
`smtplib`, so the transport is proven to speak the protocol rather than proven
to satisfy a fake. A suite built entirely on stubs asserts that one model of
SMTP matches another model of SMTP, and passes just as happily when both are
wrong.

## Licence

Apache-2.0
