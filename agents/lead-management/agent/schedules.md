# Scheduled runs

Each entry is a schedule the agent runs on its own. `rrule` is an iCal recurrence.

## Daily sweep

- rrule: `FREQ=DAILY;BYHOUR=9;BYMINUTE=0` (America/New_York)
- delivery: slack_dm, read-only: False, alert mode: False

```text
Daily sweep. The catch-up and reconcile pass. Webhooks handle inbound in real time; this pass exists to run scheduled touches and to catch whatever the webhooks missed.

1. RECONCILE FIRST. Before anything else, find what the webhooks did not deliver:
   - Instantly replies from the last 24h with no ledger row. Run the full triage loop on each.
   - Close leads created in the last 24h with no first touch logged. Contact immediately and log the delay in speed_miss_reason as "webhook not received."
   - Cal.com bookings, cancellations and no-shows from the last 24h not reflected in Close. Set Product Line from the event type. Start the matching sequence.
   - Poll the Neon public.vapi_conversations table once for rows above the last high-water mark. This is the safety net behind the Vapi webhook, which is the primary path.
   Anything found here is a webhook failure. Name it in the Slack confirmation so the gap gets fixed rather than absorbed.

2. ENRICHMENT GAP-CHECK. Enumerate Close leads that have a business domain but empty Google Rating / Review Count (skip Customer / Bad Fit / Not Interested and free-mail/junk domains). These are leads enrichment missed, regardless of how they arrived — Instantly and Supabase are inputs, not the trigger. Resolve cache-first against Supabase investor_prospects (free, via supabase__execute_sql), then a fresh Apify Google Maps lookup for misses. ALWAYS domain-verify a fresh result (accept only when its website domain matches the lead's domain, since name-only search returns the wrong cash-buyer business). Write Google Rating / Review Count / Categories + Market to Close and set Enrichment Provenance/Summary honestly, including "no matching listing" when that is the outcome. Keep cost discipline (cache-first, one lead at a time).

3. EXECUTE-DUE. For every approved per-lead plan, send every touch due today. Reason the channel per touch: email for depth (proof points, VSL, numbers), SMS for short nudges and same-day reminders, both only when both add value and do not duplicate. Send via the brand-matched channel: Instantly reply-to-email for cold-email replies; close-crm send-email with the brand email-account-id for form leads; close-crm send-sms for SMS. Log a Close note per send.

4. PLAN-NEW-LEADS. For leads that entered a sequence since yesterday and do not yet have a plan, generate one multi-day plan each (touches, cadence, per-touch channel, angles) and post it to Alex's Slack DM. State who the lead is (name and brand), why (sequence state), and the approach. If he says nothing, run it. This checkpoint never sits in front of a first touch; the first touch has already gone out.

5. GUARDRAILS, re-checked before every send. Skip Customer, Bad Fit, Not Interested, Disqualified, inactive (post-breakup, two no-shows, explicit opt-out), and referrals. Exception: a live uncancelled Cal.com booking overrides all of these. Send, and flag the contradiction separately. Brand identity never crossed. Do not pre-filter on budget tier or inferred fit before we have spoken.

6. LEDGER. Write the day's rows, including inbound_at, first_touch_at, minutes_to_first_touch and speed_miss_reason on every first touch.

Then post to Alex's Slack DM: what went out (lead, brand, channel, one line each), any webhook gaps found in step 1, how many leads the enrichment gap-check enriched and how many had no listing, new plans awaiting his review, anything escalated, and the day's speed numbers (how many first touches, median minutes, and any miss over 5 minutes with its reason). If nothing went out, say so in one sentence.
```

## Hourly reply triage

- rrule: `FREQ=HOURLY;BYDAY=MO,TU,WE,TH,FR;BYHOUR=9,10,11,12,13,14,15,16,17;BYMINUTE=0` (America/New_York)
- delivery: thread, read-only: False, alert mode: True

```text
Triage new Instantly replies.

Pull replies from roughly the last 90 minutes — a deliberate overlap on the hourly window so nothing falls through a boundary. This run is stateless, so the overlap WILL re-surface replies you already handled. That is expected: the dedup check in your loop is what prevents duplicate drafts and duplicate sends, not a narrow time window. Run it on every single reply before you draft or send anything.

For each genuine, not-yet-handled human reply: halt the sequence in Instantly, read the reply honestly, pull Close history via find-lead and last-touch, enrich the lead per the intake rule (cache-first, then domain-verified fresh lookup; populate Google Rating / Review Count / Categories / Market when the data exists), draft from the correct brand mailbox, SEND via Instantly reply-to-email (auto-send is on), and update Close with honest status plus a note that identifies which reply you were responding to. Enforce the guardrails: skip Customer / Bad Fit / Not Interested leads and referrals. Post what went out to Slack.

Skip auto-replies and out-of-office bounces — mark them and move on; they are not engagement.

Keep this pass tight: one sweep of the replies endpoint with a sane limit, no looping or re-polling. If there are no new replies, finish silently.
```

## Weekly campaign performance report

- rrule: `FREQ=WEEKLY;BYDAY=MO;BYHOUR=9;BYMINUTE=0` (America/New_York)
- delivery: thread, read-only: True, alert mode: False

```text
Generate the Monday morning campaign performance report for Alex. Pull stats for each active Instantly campaign, compare week-over-week, flag anomalies. Report in Slack #leads. Keep it tight — Alex wants the headlines and the anomalies, not a novel.
```

## Neon VAPI conversation poll

- rrule: `FREQ=HOURLY;BYDAY=MO,TU,WE,TH,FR;BYHOUR=8,9,10,11,12,13,14,15,16,17,18,19,20;BYMINUTE=0` (America/New_York)
- delivery: slack_dm, read-only: False, alert mode: True

```text
Poll the Neon database for new VAPI phone/chat conversations and triage them into Close CRM.

Read the high-water-mark memory (query: "Neon vapi_conversations high-water mark") for the last processed id; if none, start at 0.

Query Neon via the neon-data skill (FetchSkillScripts then RunWithCredentials), one statement:
SELECT id, kind, vapi_id, assistant_id, status, ended_reason, customer_number, duration_seconds, message_count, transcript, summary, qualification_score, appointment_booked, structured_outputs, lead_id, created_at FROM public.vapi_conversations WHERE id > <hwmark> ORDER BY id ASC

For each NEW conversation (id > high-water mark), the intent is a lead who talked to a VAPI phone or chat agent. Figure out who they are: if lead_id is set, join public.leads; otherwise match customer_number against Close via find-lead-by-phone. Then treat it like a new lead: enrich the lead per the intake rule (cache-first, then domain-verified fresh lookup; populate Google Rating / Review Count / Categories / Market when the data exists), log an honest Close note summarizing the conversation (kind, status, ended reason, qualification score, appointment booked, concise summary), set honest status, and flag anything needing Alex's attention. Email/sms follow-up is sent on your judgment (auto-send is on), but enforce the guardrails: skip Customer / Bad Fit / Not Interested / Disqualified leads, inactive leads, and referrals. Escalate pricing/scope/annoyed threads.

If a conversation has no matching Close lead and no resolvable identity, log a brief thread note rather than fabricating a CRM record.

Update the high-water-mark memory to the max id you processed. Dedupe: if a vapi_id already appears in a Close note from you, skip it.

If no new rows, finish silently.
```
