# Agent blueprints

Working AI agents from White Space Solutions, published so you can copy them.
Each one is a real agent that runs a real business process, with the client
data removed and the business specifics turned into placeholders. You get the
system prompt, the skills, the knowledge skeleton, the guardrails, and a
checklist for everything that has to be set by hand.

They are built for [Hyperagent](https://hyperagent.com/refer/7ULNHFZM) and
import there in one step. The prompt and the skills are plain markdown, so
they also work as the instructions for any capable model.

**No coding required to use the first agent.** If you can fill in a form and
paste text, you can have it running.

## What is in the box

| Agent | What it does |
|---|---|
| [`agents/lead-management/`](agents/lead-management/) | Front line for inbound replies, form fills, voice calls and bookings across two brands. Triages, enriches, keeps the CRM current, decides the next touch, books the call. One metric: qualified calls booked. |

More will follow (Meta ads, underwriting, property ops) as they are cleaned up.

Around the agents:

- [`FRAMEWORK.md`](FRAMEWORK.md): the six words every agent here is described in (role, responsibilities, skills, tools, knowledge, guardrails).
- [`job-card.md`](job-card.md): the six questions to answer before building any agent, blank and then filled in for the lead agent. **Start here** if you are adapting this to your own business.
- [`skills/`](skills/): the shared skill library. `doctrine/` is instructions with no code (how to qualify, which sequence a lead is in, how to write). `clients/` wraps an API (Close, Instantly, Cal.com, Vapi, Neon, Apify) with a script and the credential it needs.
- [`docs/post-import-checklist.md`](docs/post-import-checklist.md): what the import cannot carry.

## Three ways to use it

### 1. Import into Hyperagent (the way it was built)

About 30 minutes, no code.

1. Open [Hyperagent](https://hyperagent.com/refer/7ULNHFZM) and create an
   agent from a file. Pick
   [`agents/lead-management/agent/lead-management.json`](agents/lead-management/agent/lead-management.json)
   (download the raw file from GitHub first).
2. The prompt, all eleven skills, the four schedules and the four webhook
   definitions arrive with it.
3. Work through [`docs/post-import-checklist.md`](docs/post-import-checklist.md).
   The short version: paste your API keys into each client skill, pick a
   model, connect your apps, create the webhook endpoints, pin your Game Plan
   as a context file.
4. Replace the placeholders (table below). Hyperagent's prompt editor has
   find and replace; so does any text editor.
5. Turn every schedule on in **read-only mode** for a week. Read what it would
   have done. Then turn writes on.

### 2. Run it on any AI model (Claude, ChatGPT, Gemini, a local model)

The prompt and the doctrine skills are just text. Any model that takes a
system prompt can run the judgment half of this agent today; the API half
needs tooling, which is what Hyperagent provides.

1. Open [`agents/lead-management/agent/system-prompt.md`](agents/lead-management/agent/system-prompt.md).
   Paste it as the **system prompt** (Claude Projects: "Project instructions".
   ChatGPT: a custom GPT's "Instructions". API: the `system` field).
2. Add the five files in [`skills/doctrine/`](skills/doctrine/) as **project
   knowledge** or attached files. These are the rules: qualification,
   sequencing, email and SMS voice, Slack formatting.
3. Add your own Game Plan (start from
   [`knowledge/lead-management-game-plan.md`](agents/lead-management/knowledge/lead-management-game-plan.md))
   the same way.
4. Replace the placeholders (table below) in what you pasted.
5. Paste a real inbound reply and say "triage this." You will get the
   classification, the sequence, the draft, and what it would log. That is
   the agent with a human doing the sends.

To make it act on its own (send the email, update the CRM) you need tools.
The scripts in [`skills/clients/`](skills/clients/) are the ones this agent
uses; a developer, or an agent platform like Hyperagent or Claude Code, can
wire them up. Each `SKILL.md` says exactly how it is called.

### 3. Let an AI adapt it to your business first

The fastest path if your business does not look like the example. Give a
capable model the repo and this prompt:

> I want to build the agent in this repo for my business. Read
> `FRAMEWORK.md`, `job-card.md`, and `agents/lead-management/`. Then interview
> me with the six job-card questions, one at a time, and write my answers into
> a filled-in job card. When the card is complete, rewrite
> `agents/lead-management/agent/system-prompt.md` for my business: replace
> every placeholder from the README table, drop any product line or brand I
> do not have, and keep every guardrail. Show me the diff before you change
> anything else.

Claude Code, Cursor, and similar tools can do this against a clone of the
repo. A chat model can do it if you paste the three files in.

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
rewriting that skill; the doctrine skills do not care what you run.

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

## Publishing your own

`tools/sanitize-export.py` turns a raw Hyperagent export into an `agents/`
folder in two passes. First it replaces secrets, record ids, phone numbers
and real names using a gitignored map (`tools/redactions.example.json` shows
the shape). Then it applies `tools/normalize.json`, the committed list of
generalizations that turn one company's definitions (product lines, booking
slugs, industry words) into the placeholders above. It refuses to write if
anything secret-, id- or brand-shaped survives (`tools/forbidden.example.txt`).
Raw exports never touch git.

## Questions

Open an issue, or email jason@whitespacesolutions.ai.

---

Jason Macht, [White Space Solutions](https://www.whitespacesolutions.ai).
The Hyperagent link above is a referral link.
