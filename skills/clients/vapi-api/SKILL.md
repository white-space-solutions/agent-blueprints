---
name: vapi-api
description: "Vapi.ai voice AI platform \u2014 create and manage outbound voice calls, receive real-time call events via webhooks, and integrate voice calling into lead management workflows. Supports creating calls, fetching call details, listing calls, and processing webhook events from VAPI."
when_to_use: "Use for anything involving VAPI voice calls: creating outbound follow-up calls to leads, checking call status, listing recent calls, or processing incoming VAPI webhook events (status updates, transcripts, end-of-call reports). The webhook_handler.py script parses raw VAPI events into actionable JSON with interest/negative signal detection."
tags: ["vapi","voice","calling","outbound","webhook","lead-management","telephony"]
auth: api_key
---
# VAPI Voice Calling API

Vapi.ai voice AI platform — create and manage outbound/inbound voice calls, receive real-time call events via webhooks, and integrate voice calling into lead management workflows.

## Setup

Requires `VAPI_API_KEY` — a VAPI private API key from the [Vapi Dashboard](https://dashboard.vapi.ai) (Settings → API Keys). Also requires a configured VAPI phone number and assistant.

## API Base

All requests go to `https://api.vapi.ai`. Authentication is via `Authorization: Bearer <VAPI_API_KEY>`.

**Critical:** VAPI sits behind Cloudflare and rejects requests whose User-Agent is not browser-like (HTTP 403, `error code: 1010`). Every script sends a browser User-Agent header automatically. If you see a 403 with error 1010, it is NOT an auth failure — do not re-enter the API key.

## Scripts

### create_call.py

Create an outbound phone call. Required: `--to` (customer number, E.164 format). At minimum also needs `--assistant-id` or `--squad-id`.

```
python3 create_call.py --to "+14155552671" --assistant-id "assistant_abc123" --phone-number-id "pn_xyz789"
```

Options:
- `--to`: Customer phone number (E.164, required)
- `--assistant-id`: Saved VAPI assistant ID
- `--phone-number-id`: VAPI phone number to call from
- `--first-message`: Override the assistant's first spoken message
- `--squad-id`: Squad ID (alternative to assistant)
- `--customer-name`: Name for personalization
- `--context`: JSON string with arbitrary metadata

If no `--assistant-id` is given but `--first-message` is, a transient assistant is built automatically with a real-estate-services follow-up system prompt.

### get_call.py

Retrieve a call by ID to check status, get transcript, or review artifacts.

```
python3 get_call.py <call_id>
```

Returns full call object: status, customer, assistant, transcript, recording URLs, cost, timing, analysis.

### list_calls.py

List recent calls, optionally filtered.

```
python3 list_calls.py --limit 20 --status ended --assistant-id assistant_abc123
```

Options: `--limit` (default 10), `--assistant-id`, `--status` (scheduled, queued, ringing, in-progress, forwarding, ended).

### list_assistants.py

List VAPI assistants (phone and chat agents), or fetch one by ID.

```
python3 list_assistants.py --limit 25
python3 list_assistants.py --id assistant_abc123
```

Options: `--limit` (default 25), `--id` (fetch a single assistant).

This closes the "visibility into phone and chat agents" gap. VAPI's MCP server exposes `list_assistants` / `get_assistant`; this script reproduces that surface over the REST API (`GET /assistant` and `GET /assistant/{id}`).

### webhook_handler.py

Process a VAPI webhook event payload file into a structured JSON summary the agent can act on.

```
python3 webhook_handler.py /path/to/webhook_event.json
```

Handles these event types:
- `status-update`: Call status changed — returns new status
- `end-of-call-report`: Call completed — returns summary, ended reason, transcript, success evaluation. Also flags interest/negative signals for agent action.
- `transcript`: Real-time transcript snippet
- `hang`: Assistant failure — flagged for immediate attention

Output fields include `requires_action` (boolean) and `action_note` (what the agent should do).

## Webhook Integration Architecture

### Receiving VAPI Events in Hyperagent

VAPI sends POST requests to a configured Server URL. The flow:

1. **Configure the Hyperagent webhook URL in VAPI** — Set it at the Account-level in VAPI Dashboard (Settings → General → Server URL), or on a specific Assistant.
2. **VAPI POSTs events** → Hyperagent webhook starts a new agent thread with the event body as the prompt.
3. **Agent processes the event** → Writes the event JSON to a file, runs `webhook_handler.py` to parse it, then takes action based on `requires_action` and `action_note`.

### Processing Pattern (Agent Instructions)

When a VAPI webhook event arrives in a new thread:

1. Write the event body to `/tmp/vapi_event.json`
2. Run: `python3 /agent/workspace/skills/vapi-api/webhook_handler.py /tmp/vapi_event.json`
3. Read the output. If `requires_action` is true:
   - For `end-of-call-report` with interest signals: Log to Close CRM as a note on the lead, flag for Alex's attention via Slack DM
   - For `hang` or error events: Alert Alex via Slack immediately
   - For `status-update` with `ended`: Follow up with an end-of-call summary note in Close
   - For negative outcomes: Update Close lead status to "not interested" if confirmed
4. Always log the event to Close CRM (as a note on the matching lead, found by phone number)
5. If no matching lead is found in Close, note it and alert Alex

### Finding the Lead in Close

Match the customer phone number from the VAPI event against Close CRM leads. Use the close-crm skill to search by phone number (the `find-lead-by-phone` subcommand). If a match is found, log the call event as a note. If no match, create a note in the thread for Alex.

## Outbound Call Flow

When the agent decides to trigger an outbound follow-up call:

1. Verify the lead has a valid phone number in Close CRM
2. Run `create_call.py` with the lead's phone number and the appropriate assistant
3. Log the outbound call attempt in Close CRM as a note
4. The response includes a `call.id` — record this for matching when the webhook events arrive

## Important Notes

- VAPI webhooks require a publicly accessible HTTPS URL (Hyperagent webhook endpoints qualify)
- The `end-of-call-report` event arrives after a call ends and contains the most valuable data: summary, transcript, success evaluation, and cost
- For dynamic assistant configuration on inbound calls, respond to `assistant-request` events within 7.5 seconds — but for our outbound use case, we always specify the assistant at call creation
- VAPI charges per-minute for calls; monitor costs via `end-of-call-report.cost`
- Phone numbers must be in E.164 format (+14155552671)

## Current assistants (from a live list on 2026-08-24)

- `<vapi-assistant-id-brand-a-inbound>` — Brand A: Brand A Agent (Inbound)
- `<vapi-assistant-id-outbound>` — Brand A: Lead Gen (Outbound)
- `<vapi-assistant-id-client-a>` — Client A Agent (Inbound)
- `<vapi-assistant-id-brand-b-inbound>` — Brand A: Brand B Agent (Inbound)
- `<vapi-assistant-id-booking>` — Brand A: Booking Assistant (Outbound)
