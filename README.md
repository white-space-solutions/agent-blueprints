# Agent blueprints

Working agents from White Space Solutions, published as importable
[Hyperagent](https://hyperagent.com/refer/7ULNHFZM) exports with the client
data removed. Each one comes with its system prompt, skills, knowledge
skeleton and guardrails, plus the checklist of what to set by hand after
import.

## Agents

| Agent | What it does | Status |
|---|---|---|
| [`agents/lead-management/`](agents/lead-management/) | Front line for inbound replies, form fills, voice calls and bookings across two brands. One metric: qualified calls booked. | Live since Aug 2026 |

More rosters (Meta ads, underwriting, property ops) will land here as they
are sanitized.

## How it is organized

```
agents/<name>/        one folder per agent or roster, importable on its own
  agent/<name>.json   the sanitized export
  agent/*.md          prompt, schedules, webhooks, readable in a diff
  knowledge/          context file skeletons and normalized copy
  guardrails.md       the rules that do not bend
skills/
  doctrine/           instructions with no code: how to qualify, sequence, write
  clients/            API clients: SKILL.md, the script, the credential it reads
docs/                 post-import checklist
tools/                the sanitizer that produces every agents/ folder
talks/                where these were presented
FRAMEWORK.md          role, responsibilities, skills, tools, knowledge, guardrails
job-card.md           the six questions to answer before building any agent
```

## Placeholders

Every agent is de-branded the same way. Search and replace these and the
prompt, skills and schedules read as yours.

| Placeholder | Stands for |
|---|---|
| `Alex` | The business owner. Whoever the agent escalates to and writes as. |
| `Ava` | The outbound voice agent (Close's native call agent in this build). |
| `Brand A`, `brand-a.example.com` | A software or automation offer. |
| `Brand B`, `brand-b.example.com` | A done-with-you service offer. One brand? Delete the Brand B sentences. |
| `Brand A Automation`, `Brand A Retainer`, `Brand A Project`, `Brand A Custom`, `Brand B Service` | Product lines, the values of the CRM's `Product Line` field. |
| `brand-a-consult`, `brand-a-project-call`, `brand-b-consult`, `30min` | Cal.com event slugs, one per product line plus a fallback. |
| `<your-cal-handle>` | Your Cal.com username. |
| `owner@brand-a.example.com` | The mailbox the agent sends from. |
| `<...>` | Any record id: assistant, campaign, table, email account, webhook endpoint. |
| `owner-operators in your niche` | The ICP. Say who, in one line. |

The stack is real and named (Close, Instantly, Cal.com, Vapi, Neon, Apify,
Slack) because the client skills wrap those APIs. Swapping one means
rewriting that skill; the doctrine skills do not care.

Skills are shared across agents on purpose. Most of what transfers between
businesses is in `skills/doctrine/`.

## Start here

1. Read [`FRAMEWORK.md`](FRAMEWORK.md), then fill in [`job-card.md`](job-card.md) for one job in your business.
2. Open an agent folder. Its README says what it does and what it needs.
3. Import the JSON into Hyperagent and work through [`docs/post-import-checklist.md`](docs/post-import-checklist.md).

## Publishing your own

`tools/sanitize-export.py` turns a raw Hyperagent export into an `agents/`
folder in two passes. First it replaces secrets, record ids, phone numbers
and real names using a gitignored map (`tools/redactions.example.json` shows
the shape). Then it applies `tools/normalize.json`, the committed list of
generalizations that turn one company's definitions (product lines, booking
slugs, industry words) into the placeholders above. It refuses to write if
anything secret-, id- or brand-shaped survives (`tools/forbidden.example.txt`).
Raw exports never touch git.

---

Jason Macht, [White Space Solutions](https://www.whitespacesolutions.ai). jason@whitespacesolutions.ai

The Hyperagent link above is a referral link.
