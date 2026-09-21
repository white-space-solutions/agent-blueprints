---
name: cal-com
description: "Cal.com API v2 client for calendar operations. List event types by username, get available time slots, and create bookings. Used by the Lead Management Agent to read Alex's live availability and book calls for qualified leads \u2014 the final step in the reply-to-appointment funnel."
when_to_use: "When the agent needs to check Alex's live availability or book a call for a qualified lead \u2014 this is the final step after qualification. Use after the agent has determined which Cal.com event type applies to the conversation."
tags: ["cal-com","calendar","availability","booking","scheduling","lead-management"]
auth: api_key
---
# Cal.com API v2

Calendar platform. This skill wraps the v2 REST API for availability checks, bookings, and booking tracking — the agent's calendar spine.

**Base URL:** `https://api.cal.com/v2/`
**Auth:** `Authorization: Bearer $CAL_API_KEY`

Run everything through `RunWithCredentials` so the key is injected:

```
RunWithCredentials(skillName="cal-com", command="python3 skills/cal-com/cal_com.py <subcommand> [flags]")
```

All output is JSON on stdout. Errors print `{"error": "...", "status": N}` and exit nonzero.

## Subcommands

### `list-event-types --username X [--event-slug Y]`
List all event types for a Cal.com user. Returns id, slug, title, lengthInMinutes. Use this to discover event type IDs when you only know the slug, or to verify the event types Alex has configured.

**cal-api-version:** `2024-06-14`

### `get-availability --event-type-slug X --username <your-cal-handle> --start YYYY-MM-DD --end YYYY-MM-DD [--timezone America/New_York]`
The primary workflow: check Alex's real availability for a specific event type. Returns flattened slots with date, start, and end times. Use the `--timezone` flag to return slots in the lead's timezone.

Also works with `--event-type-id` directly if you already have the ID.

**cal-api-version:** `2024-09-04`

### `create-booking --event-type-slug X --username <your-cal-handle> --start "2026-08-18T14:00:00Z" --attendee-name "John Smith" --attendee-email "john@example.com" [--timezone America/New_York]`
Create a confirmed booking. Returns bookingUid, status, start/end, attendee email, meetingUrl, and cancelUrl.

Also works with `--event-type-id` directly.

**cal-api-version:** `2026-02-25`

### `list-bookings --status upcoming,past [--after-start T] [--before-end T] [--event-type-slugs X,Y --username <your-cal-handle>]`
List bookings from Cal.com, filtered by status and optional date range and event type slugs. Returns uid, status, title, start, end, attendees (with name, email, phoneNumber, noShow, timeZone), location, cancellationReason, createdAt, updatedAt, eventTypeId, metadata. Use for booking tracking: the daily sweep polls recent bookings and cross-checks against Close CRM to catch no-shows, confirmations, starts, and ends that need logging.

**cal-api-version:** `2026-05-01`

### `get-event-type --event-type-id X`
Get full details for a single event type by ID.

## Event type slug → Cal.com link mapping

The agent's memory stores Alex's four product-specific Cal.com links. Each link's URL path maps to an event type slug:

| Link | Slug |
|---|---|
| `cal.com/<your-cal-handle>/brand-a-project-call` | `brand-a-project-call` |
| `cal.com/<your-cal-handle>/brand-a-consult` | `brand-a-consult` |
| `cal.com/<your-cal-handle>/brand-b-consult` | `brand-b-consult` |
| `cal.com/<your-cal-handle>/30min` | `30min` |

The username is always `<your-cal-handle>`.

## Cloudflare User-Agent requirement

`api.cal.com` sits behind Cloudflare with a bot-signature filter. The script sends a normal Chrome User-Agent to pass through. If 403s return, check the UA header first.

## Booking flow — how the agent uses this skill

1. Lead shows genuine interest → agent decides which Cal.com link applies (based on brand + conversation)
2. Agent calls `get-availability` with the matching slug for the next 3-5 business days
3. Agent proposes 2-3 concrete times to the lead
4. Lead picks a time or books themselves via the link
5. If the lead asks the agent to book it, agent calls `create-booking` with the confirmed time and attendee details
6. Agent reports the booking confirmation to the lead and logs it in Close CRM

## Booking tracking — how the agent uses `list-bookings`

Cal.com sends SMS/email reminders and pre-call confirmation calls. The agent cannot receive Cal.com webhooks directly, so the daily sweep polls `list-bookings` to track booking lifecycle events:

1. Daily sweep calls `list-bookings --status upcoming,past --after-start <24h ago> --event-type-slugs <all four> --username <your-cal-handle>`
2. For each booking returned, cross-checks against Close CRM activity timeline
3. Booking confirmed (new uid not in CRM) → log note
4. Booking no-show (attendee.noShow=true) → log note, trigger one follow-up draft
5. Booking cancelled (status=cancelled) → log note with cancellationReason, update lead status
6. Meeting started/ended (booking start < now, no activity logged yet) → log note

## API key requirements

The API key must be generated at [Cal.com Settings → Developer → API Keys](https://app.cal.com/settings/developer/api-keys). It must have read access to event types, slots, and bookings, and write access to bookings. The key begins with `cal_live_`.

## Rate limits

No published rate limits in the v2 docs. The script retries 429s with exponential backoff up to 4 times.
