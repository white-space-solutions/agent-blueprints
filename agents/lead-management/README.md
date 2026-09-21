# Lead Management Agent

The agent from the Family Mastermind breakout (Sep 29, 2026): knowledge base
skeleton, guardrails and skills, with client data removed. Runs on
[Hyperagent](https://hyperagent.com/refer/7ULNHFZM); the JSON here imports in one step.

One agent, one job: every inbound reply, form fill, voice call and booking
for two brands runs through it, and its only metric is qualified calls booked
on the owner's calendar.

**Placeholders.** See the table in the root README. In short: the owner is
`Alex`, the outbound voice agent is `Ava`, the businesses are `Brand A` (a
software or automation offer) and `Brand B` (a done-with-you service), product
lines are `Brand A Automation / Retainer / Project / Custom` and
`Brand B Service`, booking links are `brand-a-consult`, `brand-a-project-call`,
`brand-b-consult` and `30min`, and record ids are `<...>`. One brand? Keep
Brand A and delete every Brand B sentence; the routing logic collapses
cleanly.

## What is here

| Path | What it is |
|---|---|
| `agent/lead-management.json` | The full agent export, sanitized. Import this. |
| `agent/system-prompt.md` | The system prompt on its own, so it reads in a diff. |
| `agent/schedules.md` | The four scheduled runs and what each one is told. |
| `agent/webhooks.md` | The four inbound webhook endpoints and their prompts. |
| `guardrails.md` | The safety rules, lifted verbatim from the prompt. |
| `knowledge/lead-management-game-plan.md` | The Game Plan skeleton: sections, the eight sequences and their cadences. |
| `knowledge/sequence-copy.md` | A normalized subset of the copy, with the specifics turned into slots. |
| `../../skills/` | The eleven skills this agent uses, in the shared library. |
| `../../docs/post-import-checklist.md` | What the JSON cannot carry and what to set by hand. |

## The shape of it

```
role            Front line for two brands. North star: qualified calls booked.
responsibilities  triage every inbound, enrich, keep the CRM current, decide the
                next touch, drive to a booked call, escalate what it should not decide
skills          instantly, close-crm, lead-enrichment, cal-com, vapi-api, neon-data,
                slack-format, email-copywriting, sms-copywriting, sequencing,
                lead-qualification
tools           the connected apps in allowedIntegrations, gated by toolSettings
knowledge       the Game Plan (pinned context file) and the lead activity ledger (table)
guardrails      guardrails.md
```

Skills split two ways. Six are **API clients**: a `SKILL.md` that says when and
how to call a script, plus the script, plus a credential the script reads
from its environment. Five are **pure doctrine**: instructions with no code,
where the value is in the rules (how to qualify, which sequence a lead is
in, how to write in the owner's voice). The doctrine skills are the ones to copy.

## Import it

1. In Hyperagent, create an agent from `agent/lead-management.json`.
2. Work through `../../docs/post-import-checklist.md`. Credentials, model,
   integrations, webhook secrets and the context file are not in the export.
3. Search for `<...>` placeholders in the prompt and skills and replace them.
4. Run the schedules read-only for a week before turning writes on.

## What was removed

Webhook secrets, record ids (assistant, campaign, table, email account),
one phone number, prospect names and addresses, and most of the sequence
copy. Structure, cadences, rules and voice guidance are intact, and
`knowledge/sequence-copy.md` carries a normalized sample of the copy.
`../../tools/sanitize-export.py` produced all of it and refuses to write if
anything id- or secret-shaped survives.

## Talk resources

The slides, the framework diagram and the job-card PDF are on the resources
page linked from the deck. See `../../talks/`.

---

Part of [agent-blueprints](../../README.md).
