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

Every agent is de-branded the same way: the owner is `Alex`, businesses are
`Brand A` and `Brand B`, ids are `<...>`. Search and replace, and it is yours.

Skills are shared across agents on purpose. Most of what transfers between
businesses is in `skills/doctrine/`.

## Start here

1. Read [`FRAMEWORK.md`](FRAMEWORK.md), then fill in [`job-card.md`](job-card.md) for one job in your business.
2. Open an agent folder. Its README says what it does and what it needs.
3. Import the JSON into Hyperagent and work through [`docs/post-import-checklist.md`](docs/post-import-checklist.md).

## Publishing your own

`tools/sanitize-export.py` turns a raw Hyperagent export into an `agents/`
folder. It replaces secrets, record ids, phone numbers and names using a
local, gitignored map (`tools/redactions.example.json` shows the shape) and
refuses to write if anything secret- or id-shaped survives. Raw exports never
touch git.

---

Jason Macht, [White Space Solutions](https://www.whitespacesolutions.ai). jason@whitespacesolutions.ai

The Hyperagent link above is a referral link.
