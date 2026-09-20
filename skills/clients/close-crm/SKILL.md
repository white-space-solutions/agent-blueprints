---
name: close-crm
description: "Close CRM (close.com) API client and system-of-record operations for lead management. Resolve leads from an email address, read full activity history, compute last-touch recency to drive follow-up decisions, log notes, move opportunities through pipeline stages, and enroll contacts in email sequences."
when_to_use: "Use for anything involving CRM state: looking up who a lead is, checking when we last communicated with them and what was said, deciding whether a follow-up is due, logging activity, changing pipeline stage, or enrolling someone in a sequence. Close is the source of truth for lead sentiment and pipeline position."
tags: ["close-crm","crm","pipeline","lead-management","sales","brand-a","brand-b"]
auth: api_key
---
# Close CRM API

System of record for leads, pipeline, and communication history.

**Base URL:** `https://api.close.com/api/v1`
**Auth:** HTTP Basic — base64 of `<API_KEY>:` (key, literal colon, empty password)

Run through `RunWithCredentials`:

```
RunWithCredentials(skillName="close-crm", command="python3 skills/close-crm/close_crm.py <subcommand> [flags]")
```

All output is JSON on stdout. Errors print `{"error": "...", "status": N}` and exit nonzero.

## Data model — get this right

Close separates **Lead** (the company/organization) from **Contact** (a person at that company). An inbound email address belongs to a *Contact*; the pipeline and opportunities hang off the *Lead*. Almost every workflow starts with `find-lead --email` to resolve both.

## Connected mailboxes (send-as accounts)

Two brand mailboxes are connected in Close. Map **email_account_id** to brand when sending:

- Brand B / DWY Direct Mail → `<instantly-email-account-id-brand-b>` (owner@brand-b.example.com)
- Brand A (AI Automation / AI SEO / Website / Custom Build) → `<instantly-email-account-id-brand-a>` (owner@brand-a.example.com)

## Lead statuses (guardrails)

`status_label` values carried on leads (from `find_lead_statuses`):
- `Potential`, `Qualified`, `Interested`, `Appointment Booked`, `Appointment Canceled`, `Appointment No Show` — active prospects.
- `Customer` — a paying customer. **Never email/call/SMS a Customer prospect.** HARD guardrail; check `status_label` before any send.
- `Bad Fit`, `Not Interested` — do not contact.

## Subcommands

### `find-lead --email X`
Resolves lead + contacts from an email address. **Start here** for any inbound reply. Uses the Advanced Filtering endpoint (`POST /data/search/`).

### `get-lead --id X`
Fetch a single lead by ID.

### `lead-history --id X [--limit N]`
Full activity timeline, newest first, normalized to `{type, direction, timestamp, subject, preview, user}`. Covers emails, calls, notes, SMS.

### `last-touch --id X`
Most recent inbound and outbound communication with day-deltas. **This is the follow-up decision input** — read it before deciding whether someone is due for a touch. Uses `activity_at` (when it happened), not `date_created` (when it was logged).

### `create-note --lead-id X --text "..."`
Log what happened. Do this after every meaningful action so the timeline stays honest.

### `update-lead --lead-id X [--name "..."] [--custom-fields '{"cf_XXX": "value", ...}']`
Update a lead's display name and/or custom fields. **This is the enrichment write path**. The `--custom-fields` argument takes a JSON object keyed by custom field IDs. Uses `PUT /lead/{id}/`.

### `send-email --lead-id X --status outbox --sender "Alex <owner@...>" --to addr --subject "..." --body "..." --email-account-id emailacct_XXX [--contact-id Y] [--send-in N]`
Send (or draft) an email through Close (`POST /activity/email/`). **This is the send path for Facebook/form leads** — the outbound lands on the lead's Close timeline automatically, so it stays the single email record (no Instantly split-brain).

- `--status` = `draft` (stages for review, never auto-sent), `outbox` (send now; add `--send-in 30` for a 60s-max undo window), `scheduled` (+ `--date-scheduled` ISO), `sent`/`inbox` (backfill logging).
- `--sender` = `"Name <email@domain>"` — required for outbox/scheduled/sent/inbox.
- `--email-account-id` routes brand identity (see mailbox map above). Always set it to the brand-matched account.
- `--to`, `--cc`, `--bcc` accept space-separated addresses.
- `--body` (plaintext) or `--body-html`. One of body/body-html/template-id required to send.
- `--in-reply-to-id` threads under a prior email activity id.
- `--followup-date` (ISO) auto-creates a follow-up task if no reply within the delay.

**Safety:** never `outbox` to a lead whose `status_label` is `Customer`, `Bad Fit`, or `Not Interested`. Default to `draft` unless the send is explicitly authorized.

### `send-sms --status outbox --text "..." --local-phone "+14155551234" --remote-phone "+18185556789" [--lead-id X] [--contact-id Y]`
Create and optionally send an SMS activity. `status=outbox` sends immediately (from the primary Close number `+15555550100` unless Alex names another); `status=draft` stages for review. Requires `--local-phone` (Close internal, E.164) and `--remote-phone` (recipient E.164). `--send-in` delays outbox by up to 60s. **Defaults to draft; set outbox only after approval.**

### `create-task --lead-id X [--type lead|outgoing_call] [--text "..."] [--contact-id Y] [--assigned-to user_Z] [--due-date ISO] [--date YYYY-MM-DD] [--priority high|medium] [--agent-config-id Z]`
Create a task on a lead. `--type lead` (default) = to-do (requires `--text`); `--type outgoing_call` = request a the voice agent voice call (requires `--contact-id`; note which Voice Agent in `--text`). Leave `--assigned-to` off for unassigned.

### `list-pipelines`
Pipelines with their stages/statuses. Call before any stage change.

### `create-opportunity --lead-id X --status-id Y [--value N]`
### `set-opportunity-stage --opportunity-id X --status-id Y`
### `list-sequences`
### `enroll-sequence --sequence-id X --contact-id Y --lead-id Z --email-account-id W`
### `find-lead-by-phone --phone X`
Resolve a lead + contacts from a phone number (VAPI call events). Same shape as `find-lead`.
### `search --query '<json>'`
Escape hatch for raw Advanced Filtering payloads.

## Advanced Filtering query shape

```json
{
  "query": {
    "type": "and",
    "queries": [
      { "type": "object_type", "object_type": "contact" },
      { "type": "field_condition",
        "field": { "type": "regular_field", "object_type": "contact", "field_name": "email" },
        "condition": { "type": "text", "mode": "full_words", "value": "alice@example.com" } }
    ]
  },
  "_fields": { "contact": ["id", "lead_id", "name", "emails", "title"] },
  "_limit": 10
}
```

Custom fields use `"type": "custom_field"` with `"custom_field_id": "cf_XXXX"`. Default response returns **IDs only** — pass `_fields` to get data back. Contact email is queryable only via the `has_related` → `contact_email` shape (see `find-lead` source); querying flat `contact.email` returns 400.

## Pagination

- Most list endpoints: offset-based, `_skip` + `_limit`, `has_more`.
- Advanced Filtering: cursor-based.
- Advanced Filtering caps at 10,000 objects; slice by `date_created` range for larger sets.

## Rate limits

Per endpoint group and per org (~20 RPS per key, 60 RPS org). On 429 the response carries `RateLimit: limit=X, remaining=Y, reset=Z`. **Honor `reset`, not `Retry-After`.** Some endpoints 429 unpredictably even inside the window.

## Unverified — confirm on first live use

1. **Sequence pause/unsubscribe status values** — `PUT /sequence_subscription/{id}/` accepts `status`, valid values undocumented in retrieved docs.
2. **Opportunity `value` units** — likely cents/minor units. **Verify with one test before writing real deal values** (100× error risk).
3. **SMS `local_phone`** — must be a Close internal number; verify before sending.
4. **Task `assigned_to` for the voice agent** — whether the voice agent Voice Agents surface as assignable `user_...` ids vs. UI-only is unconfirmed. Test `create-task --type outgoing_call` on a real lead.

## Resolved: find-lead contact email field path (confirmed live 2026-08-05)

Contact email lives on the related `contact_email` object, not flat on `contact`. Working shape uses `has_related` + `related_object_type: "contact_email"` + `full_words` mode (not `exact`).
