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

<!-- aither-ecosystem:start GENERATED from the ecosystem registry. Edits here are overwritten; change the registry instead. -->

## The aw family

Standalone tools that share one idea: **replace something you would otherwise have to _trust_ with something you can _check_.**

Each installs on its own, works offline, and needs no account.

| | instead of trusting | you check |
|---|---|---|
| [awdk](https://github.com/Aitherium/awdk) | a framework's idea of how your agents should run | one loop you can read, pointed at a backend you already pay for |
| [awskills](https://github.com/Aitherium/awskills) | that an agent knows your procedure | the procedure written down, versioned, and loadable by any agent |
| [awm](https://github.com/Aitherium/awm) | that memory stayed in its lane | tenant:user:project scopes, so a write cannot cross a boundary |
| [awnode](https://github.com/Aitherium/awnode) | a vendor's cloud with every prompt | a local gateway routing to backends you chose |
| [awgraph](https://github.com/Aitherium/awgraph) | that grep found everything | an AST + tree-sitter call graph an agent can traverse |
| [awgit](https://github.com/Aitherium/awgit) | that no one else is editing this file | a lease, refused at commit time if you do not hold it |
| [awseal](https://github.com/Aitherium/awseal) | that the artifact came from who you think | an Ed25519 seal — the key that verifies is not the key that forges |
| [awshare](https://github.com/Aitherium/awshare) | that the download is intact | content-addressed bundles, verified on fetch |
| [awnest](https://github.com/Aitherium/awnest) | that there is a person on the other end | a verdict with evidence, where "we could not tell" is not "yes" |
| [awnboard](https://github.com/Aitherium/awnboard) | a share link anyone who sees it can use | an invitation addressed to one person, for one gate, revocable |
| [awnix](https://github.com/Aitherium/awnix) | that the box is what you left it as | an immutable image you built, with atomic rollback |
| [awrecover](https://github.com/Aitherium/awrecover) | that the restore worked | a restore that fully lands or does not land at all |
| [awrelay](https://github.com/Aitherium/awrelay) | a SaaS in the middle of your agents | findings, alerts and coordination over your own transport |
| **awmail** _(you are here)_ | a mailbox somebody else can read | mail your agents send and receive over your own server |
| [awfind](https://github.com/Aitherium/awfind) | one vendor's idea of the web | results from whichever providers you configured |
| [awbrowse](https://github.com/Aitherium/awbrowse) | that the page said what you were told | the render, the DOM and the requests it made |
| [aitherkvcache](https://github.com/Aitherium/aitherkvcache) | a vendor's quantisation defaults | sub-byte KV cache kernels you can benchmark yourself |
| [AitherZero](https://github.com/Aitherium/AitherZero) | a pile of scripts nobody has numbered | numbered, discoverable automation with declarative playbooks |
| [AitherConnect](https://github.com/Aitherium/AitherConnect) | what a page tells your browser to do | a federated search and desktop bridge you host |
| [awreason](https://github.com/Aitherium/awreason) | a confident paragraph | the phases it went through, and every tool call it made to get there |
| [awrecurse](https://github.com/Aitherium/awrecurse) | that everything you pasted in was actually read | which slices it opened, and what it concluded from each |
| [awprism](https://github.com/Aitherium/awprism) | the first explanation that fits | the ranked alternatives, and the observation that separates them |
| [awrepl](https://github.com/Aitherium/awrepl) | what the agent believes the value is | the value, printed from the live session |
| [awresearch](https://github.com/Aitherium/awresearch) | a summary of pages nobody opened | every claim against the source it came from |
| [awkno](https://github.com/Aitherium/awkno) | that the docs site is up, or that you remember the family | the whole ecosystem in your terminal, with no network at all |

[**awnix**](https://github.com/Aitherium/awnix) is the ground floor — A Linux you can hand to an agent — immutable base, capabilities included.

## The Aitherium ecosystem

Every repository here is public. Each publishes an `aither-manifest.json` beside its page, so any surface can read every sibling's — the network is browsable from any node in it.

| repo | what it is | pages |
|---|---|---|
| [awdk](https://github.com/Aitherium/awdk) | Build AI agent fleets — 3 lines, any backend, local or cloud | [docs](https://aitherium.github.io/awdk/) |
| [awskills](https://github.com/Aitherium/awskills) | Portable agent skills — self-contained procedures an agent loads on demand | [docs](https://aitherium.github.io/awskills/) |
| [awm](https://github.com/Aitherium/awm) | A portable, scoped agent memory | [docs](https://aitherium.github.io/awm/) |
| [awnode](https://github.com/Aitherium/awnode) | A lightweight local gateway — bridges your apps to the AI backends you chose | [docs](https://aitherium.github.io/awnode/) |
| [awrun](https://github.com/Aitherium/awrun) | A priority-aware queue and dispatcher for agentic runs and ad-hoc CI builds | [docs](https://aitherium.github.io/awrun/) |
| [awgraph](https://github.com/Aitherium/awgraph) | A semantic code graph for agents — AST + tree-sitter, call graphs | [docs](https://aitherium.github.io/awgraph/) |
| [awgit](https://github.com/Aitherium/awgit) | Semantic version control on top of git — edit-ops and leases | [docs](https://aitherium.github.io/awgit/) |
| [awseal](https://github.com/Aitherium/awseal) | Sign an artifact so a stranger can verify it | [docs](https://aitherium.github.io/awseal/) |
| [awshare](https://github.com/Aitherium/awshare) | Publish an artifact and fetch it back verified | [docs](https://aitherium.github.io/awshare/) |
| [awnest](https://github.com/Aitherium/awnest) | Prove there is a human before you let them into the nest | [docs](https://aitherium.github.io/awnest/) |
| [awnboard](https://github.com/Aitherium/awnboard) | A front gate you can put in front of anything, and hand someone the key to | [docs](https://aitherium.github.io/awnboard/) |
| [awnix](https://github.com/Aitherium/awnix) | A Linux you can hand to an agent — immutable base, capabilities included | [docs](https://aitherium.github.io/awnix/) |
| [awrecover](https://github.com/Aitherium/awrecover) | Labelled snapshots with an all-or-nothing restore | [docs](https://aitherium.github.io/awrecover/) |
| [awrelay](https://github.com/Aitherium/awrelay) | Portable agent messaging — findings, alerts, coordination | [docs](https://aitherium.github.io/awrelay/) |
| **awmail** _(you are here)_ | Give an agent an email address — send, and actually receive | [docs](https://aitherium.github.io/awmail/) |
| [awfind](https://github.com/Aitherium/awfind) | A portable search client — query, results, ranking | [docs](https://aitherium.github.io/awfind/) |
| [awbrowse](https://github.com/Aitherium/awbrowse) | A portable browser client — navigate, console, network, DOM, screenshot | [docs](https://aitherium.github.io/awbrowse/) |
| [aitherkvcache](https://github.com/Aitherium/aitherkvcache) | Near-optimal KV cache quantization for LLM inference — sub-byte compression | [docs](https://aitherium.github.io/aitherkvcache/) |
| [AitherZero](https://github.com/Aitherium/AitherZero) | PowerShell 7+ automation framework — numbered, self-describing scripts | [docs](https://aitherium.github.io/AitherZero/) |
| [AitherConnect](https://github.com/Aitherium/AitherConnect) | Browser extension — federated AI search, page context, and the Living OS overlay | [docs](https://aitherium.github.io/AitherConnect/) |
| [awreason](https://github.com/Aitherium/awreason) | A portable reasoning client — sessions, phases, thoughts, and the chain that produced the answer | [docs](https://aitherium.github.io/awreason/) |
| [awrecurse](https://github.com/Aitherium/awrecurse) | Answer a question over a context far larger than the window — recursively, with the trace kept | [docs](https://aitherium.github.io/awrecurse/) |
| [awprism](https://github.com/Aitherium/awprism) | Turn a failure into ranked hypotheses — and say what would confirm each one | [docs](https://aitherium.github.io/awprism/) |
| [awrepl](https://github.com/Aitherium/awrepl) | A REPL an agent can actually use — state that survives between turns | [docs](https://aitherium.github.io/awrepl/) |
| [awresearch](https://github.com/Aitherium/awresearch) | Ask a research question, get a cited report you can check | [docs](https://aitherium.github.io/awresearch/) |
| [awkno](https://github.com/Aitherium/awkno) | The man page for the Aither World — every brick, stack and law, offline | [docs](https://aitherium.github.io/awkno/) |

<!-- aither-ecosystem:end -->
