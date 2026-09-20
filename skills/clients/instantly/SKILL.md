---
name: instantly
description: "Instantly.ai v2 API client for cold email campaign management. Poll for inbound replies, read and update lead interest status, halt sequences for leads who replied, and enroll new leads in campaigns. Built for the Lead Management Agent's reply-triage loop across the Brand A and Brand B campaigns."
when_to_use: "Use whenever you need to see who replied to a cold email campaign, check or change a lead's interest status in Instantly, stop a lead from receiving further sequence steps (always do this the moment a human replies), or add a lead to a campaign. This is the entry point for inbound lead flow."
tags: ["instantly","cold-email","lead-management","outbound","brand-a","brand-b"]
auth: api_key
---
# Instantly.ai v2 API

Cold email platform. This skill wraps the v2 REST API for the inbound-reply half of the workflow.

**Base URL:** `https://api.instantly.ai`
**Auth:** `Authorization: Bearer $INSTANTLY_API_KEY`

Run everything through `RunWithCredentials` so the key is injected:

```
RunWithCredentials(skillName="instantly", command="python3 skills/instantly/instantly.py <subcommand> [flags]")
```

All output is JSON on stdout. Errors print `{"error": "...", "status": N}` and exit nonzero.

## Subcommands

### `list-campaigns`
Returns campaign id, name, status. **Campaign of origin is the primary brand-routing signal** — map each campaign id to Brand A or Brand B before triaging replies.

### `list-replies --since <7d|ISO8601> [--campaign-id X] [--limit N]`
The workhorse. Returns inbound replies only (`email_type=received`), each with lead email, campaign id, subject, body text, timestamp, thread id, and `is_auto_reply`.

**Always check `is_auto_reply`** — out-of-office bounces should not be treated as engagement or trigger a human-style response.

### `get-lead --email X`
Full lead record including interest status and custom variables. Costs two API hops (email → UUID → record); the script handles this.

### `update-lead --email X [--interest-status N]`
### `pause-lead --email X`
### `add-lead --campaign-id X --email Y [--first-name] [--last-name] [--company]`

## Interest status enum (`lt_interest_status`)

| Value | Meaning |
|---|---|
| `1` | Interested |
| `2` | Meeting Booked |
| `3` | Meeting Completed |
| `4` | Won |
| `0` | Out of Office |
| `-1` | Not Interested |
| `-2` | Wrong Person |
| `-3` | Lost |
| `-4` | No Show |

## Rate limits

`GET /api/v2/emails` is capped at **20 requests/minute** — materially lower than other endpoints. Since `list-replies` hits it with cursor pagination, keep `--limit` sane (≤200 per sweep) and don't run reply polls in a tight loop. Other endpoints have no published numeric limit. The script retries 429s with backoff honoring `Retry-After`.

## Known gaps — read before relying on these

1. **There is no true "pause lead" endpoint.** `pause-lead` sets interest status to `-1` (Not Interested), which halts sends as a side effect. This is the documented-behavior workaround, not a first-class API. It also means the lead now reads as "Not Interested" in the Instantly UI even if they were enthusiastic — so **Close CRM, not Instantly, is the source of truth for real lead sentiment.** Set the honest status in Close.
2. No campaign-specific suppression exists without changing interest status.
3. The `body` field is not clearly split into HTML vs plain text in the v2 schema. The script surfaces it as `body_text`. If a reply body comes back as HTML soup, strip tags before reasoning over it.
4. General (non-email) endpoint rate limits are undocumented.

## Pagination

Cursor-based: `starting_after` request param, `next_starting_after` in the response. Max 100 items per page. The script paginates internally up to `--limit`.

## Cloudflare User-Agent requirement (found 2026-08-05)

`api.instantly.ai` sits behind Cloudflare with a bot-signature filter. urllib's default
`User-Agent: Python-urllib/3.x` is banned, so **every** request returned:

```
HTTP 403 error_code 1010 browser_signature_banned
"The site owner has blocked access based on your browser's signature."
```

The payload says "Do not retry" and `retryable: false`, which is accurate for the UA that was
sent but misleading as a diagnosis: it is not a key, quota, or IP problem. The script now sends a
normal Chrome UA and all endpoints work. If this skill ever starts returning blanket 403s again,
check the `User-Agent` header first before touching the API key.

## Sending replies: `reply-to-email` (added 2026-08-05)

The only send path in this skill. Threads an in-thread reply onto an inbound email via
`POST /api/v2/emails/reply`.

```
python3 skills/instantly/instantly.py reply-to-email \
  --eaccount owner@brand-b.example.com \
  --reply-to-uuid <reply-uuid> \
  --subject "Re: inherited house in Springfield" \
  --body-file /tmp/reply.txt \
  --confirm-send
```

- `--reply-to-uuid` is the `id` field of the inbound email, exactly as returned by
  `list-replies`. Instantly threads off that id, so the prospect sees a normal continuation.
- `--eaccount` must be the same connected mailbox the thread is already on. Replying from a
  different domain breaks threading and looks broken to the lead.
- Prefer `--body-file` over `--body-text` for anything multi-line; it avoids shell quoting damage.
- The script sends both `body.text` and `body.html`. Instantly renders the HTML part and
  **collapses plain newlines**, so the script HTML-escapes the copy and converts `\n` to `<br/>`
  automatically. Do not pre-format the file with `<br/>` tags.

### The `--confirm-send` gate

**Nothing sends without `--confirm-send`.** Without the flag the command prints the exact payload
it would POST and exits 0. This is intentional and should stay: a prospect-facing send is not
retryable, and the standing rule for this agent is draft, then human approval, then send.

Do not add `--confirm-send` to a command on your own initiative. It goes in only when the human
has approved that specific copy, or has explicitly moved this workflow to auto-send.

### Required scope

The API key needs one of `emails:create`, `emails:all`, `all:create`, `all:all`. If a send returns
403 with a scope complaint (rather than the Cloudflare 1010 above), the key was minted read-only
and needs regenerating with create scope.

## Campaign config: `get-campaign` and `update-campaign` (added 2026-08-14)

### `get-campaign --id X`
`GET /api/v2/campaigns/{id}`. Full config including the whole sequence.

### `update-campaign --id X --patch-file P --snapshot-dir D [--confirm-apply]`
`PATCH /api/v2/campaigns/{id}`. Partial update, and the only write path for
sequence copy.

```
python3 skills/instantly/instantly.py update-campaign \
  --id <campaign-id> \
  --patch-file patch.json \
  --snapshot-dir campaign_snapshots \
  --confirm-apply
```

**Two gates, both deliberate:**
- `--snapshot-dir` is **required**. The pre-change campaign is written there before
  anything is touched. That file is the rollback, and rolling back means PATCHing
  its `sequences` and `auto_variant_select` back. Editing a live sequence changes
  what every future recipient receives, so a rollback must exist first.
- Nothing applies without `--confirm-apply`. Without it the payload is printed and
  the command exits 0.

### Payload shape gotchas (confirmed live)
- `sequences` is an array but **only the first element is used**. Put all steps in
  `sequences[0].steps`.
- Every step needs `type` (must be `email`), `delay`, and `variants`. Every variant
  needs `subject` and `body`. Omit any of these and the API rejects the payload.
- `delay` is the wait **before the next** email, not before this one.
- `auto_variant_select` is nullable. Send `null` to switch it off — there is no
  "off" enum value, the enum is only `reply_rate` / `click_rate` / `open_rate`.
  After a successful null the field comes back **absent** from the response rather
  than present-and-null, which is the correct success signal.
- A PATCH containing only `sequences` leaves schedule, email_list, daily_limit and
  status untouched. Verified by diffing before and after.

### Judgement note carried forward
`auto_variant_select: {trigger: reply_rate}` is an actively harmful default on a
campaign whose replies are not the goal. On the Brand B buyer campaign it was
promoting whichever variant most successfully misled people, because misleading
people is what produced replies. If you see it set on a campaign, ask what the
reply actually indicates before trusting it.

## Webhook subscriptions: `webhooks.py` (added 2026-08-21)

The Lead Management Agent receives real-time `reply_received` events via a webhook rather than polling. The helper script wraps the webhook endpoints:

```
python3 skills/instantly/webhooks.py list
python3 skills/instantly/webhooks.py event-types
python3 skills/instantly/webhooks.py create --url URL [--event reply_received] [--name N] [--secret S]
python3 skills/instantly/webhooks.py patch --id ID [--url URL] [--secret S]
python3 skills/instantly/webhooks.py test --id ID
python3 skills/instantly/webhooks.py delete --id ID
```

### Canonical target (correct as of 2026-08-21)

- **URL:** `https://hyperagent.com/api/webhooks/<webhook-endpoint-id>/receive`
- **Secret header name:** `X-Hyperagent-Webhook-Secret`
- **Secret value:** `<HYPERAGENT_WEBHOOK_SECRET>`

### Two gotchas that cost a round-trip on first setup

1. **Hyperagent webhook endpoints authenticate via `X-Hyperagent-Webhook-Secret`, NOT `Authorization: Bearer`.** Sending a Bearer header returns `{"error":"Missing X-Hyperagent-Webhook-Secret header"}` and 401. Always set the custom header in the webhook's `headers` object.
2. **Instantly's `/test` endpoint does NOT attach custom delivery headers**, so it will always 401 against a Hyperagent endpoint even when the webhook is correctly configured. To verify, POST directly to the URL with curl and confirm a `202 accepted`:

```
curl -X POST https://hyperagent.com/api/webhooks/<id>/receive \
  -H 'Content-Type: application/json' \
  -H 'X-Hyperagent-Webhook-Secret: <secret>' \
  -d '{"event_type":"reply_received"}'
```

### Existing subscriptions (as of 2026-08-21)

- `01a024ae-...` → Hyperagent `reply_received` (canonical, the one this agent acts on).
- `019fbf0e-...` → Vercel relay (agent is OFF, left in place by owner; ignore).
- `0199e62f-...` → Make.com hook (posts Slack notifications; left in place by owner).

A single reply currently fans out to all three. Do not delete the Vercel or Make hooks without Alex's explicit go-ahead — they feed Slack notifications he still wants. When triaging a webhook wake, dedupe on the Instantly reply id so a reply that also fires Make/Vercel isn't double-handled.
