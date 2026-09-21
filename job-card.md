# The agent job card

Six questions to answer before building any agent. One page. If you cannot
fill a box in a sentence or two, the agent is not ready to build; the gap is
in the business, not the tooling.

The blank card is first. The lead management agent's card follows it, filled
in, so you can see what a complete answer looks like.

---

## The card

**Agent name:** ____________________

### 1. Role

Who is this, in one sentence a new hire would understand? What starts a run,
and what has to exist when the run is over?

> ______________________________________________________________________

### 2. Responsibilities

What is it accountable for, listed as verbs? And the one number that says it
did the job. Not activity ("replies sent"), the outcome ("calls booked").

> ______________________________________________________________________
>
> **The number:** ____________________

### 3. Skills

What does it need to know how to do, as written instructions it can follow?
Split them: doctrine (rules and judgment, no code) and clients (a script that
talks to a system). Who owns each piece of doctrine today, and where does it
live?

> Doctrine: ____________________________________________________________
>
> Clients: _____________________________________________________________

### 4. Tools

Which systems does it read, and which does it write to? Every write is a
place it can do damage; name the approval gate. What must be deterministic
(money, dates, thresholds) and therefore lives in a script the model calls
but never reasons about?

> Reads: _______________________________________________________________
>
> Writes (and the gate): _______________________________________________
>
> Deterministic: _______________________________________________________

### 5. Knowledge

What documents does it work from? Who owns them, how do they change, and what
does it do when they are silent on a question?

> ______________________________________________________________________

### 6. Guardrails

What must it never do, whatever the input says? What does it escalate to a
human, every time? What is the one failure that would be worse than doing
nothing?

> Never: _______________________________________________________________
>
> Always escalate: _____________________________________________________
>
> Worse than nothing: __________________________________________________

---

## Worked example: the lead management agent

The agent in `agents/lead-management/`. Placeholders as in the rest of the
repo: the owner is Alex, the businesses are Brand A and Brand B.

**Agent name:** Lead Management Agent

### 1. Role

Alex's front line for two brands. A run starts when a reply, form fill, voice
call or booking arrives (webhook) or on the daily sweep (schedule), and ends
with the CRM truthful, the next touch decided, and anything needing Alex's
judgment in his Slack DM.

### 2. Responsibilities

Triage every inbound reply. Enrich the lead. Keep Close current (status,
product line, reply class, qualified, a note a stranger could reconstruct the
conversation from). Decide which sequence the lead is in and what touch is
due. Draft in Alex's voice. Book the call. Log every touch to the ledger.
Escalate what it should not decide.

**The number:** qualified calls booked on Alex's calendar. Second number,
watched daily: minutes from inbound to first touch, target under five.

### 3. Skills

Doctrine (no code): `lead-qualification` (is this a fit, what do they need,
book or not), `sequencing` (which lifecycle sequence, what touch is due),
`email-copywriting` and `sms-copywriting` (Alex's voice, the banned phrases,
the P.S. rule), `slack-format`. Owned by Alex; edited as skills, not as
prompt changes.

Clients (script plus credential): `instantly` (replies, campaigns, sends),
`close-crm` (leads, notes, tasks, SMS through Close), `cal-com` (event types,
live slots, bookings), `vapi-api` (call events and transcripts),
`lead-enrichment` (website and company lookup), `neon-data` (the website's
lead and conversation tables).

### 4. Tools

Reads: Instantly, Close, Cal.com, Vapi, the Neon lead tables, live calendar
availability, call notes, Slack.

Writes (and the gate): Close records and notes (unattended, it is the system
of record and every write is logged). Outbound email through the brand's Close
mailbox and SMS through Close (unattended inside business hours, hard stop on
any opt-out, never through Gmail). Proposals, pricing, contracts: never; it
surfaces and hands off. Voice re-engage after a no-show: once, then a human.

Deterministic: cadence day counts, quiet hours, the do-not-contact check
before every send, speed-to-lead minutes. Computed, never estimated.

### 5. Knowledge

The Lead Management Game Plan, pinned as a context file: principles, the
eight sequences with cadences and copy, SMS rules, brand routing, the
reference facts (ids, links). Owned by Alex, changed by editing the document,
never by the agent remembering something. When the Game Plan and the prompt
disagree on a specific, the Game Plan wins. When both are silent, it asks
Alex rather than inventing a rule.

### 6. Guardrails

Never: send through Gmail; send a price, discount, term or scope; contact
anyone in the do-not-contact set (customers, disqualified, gone dark, two
no-shows); blur the two brands; stack channels on the same day; bluff past a
gap; invent a calendar slot.

Always escalate: pricing, contracts, scope, an annoyed thread, a competitor,
a partner, a recruiter, a brand crossover, a contradiction in the record.

Worse than nothing: a duplicate draft in Alex's outbox, a wrong send to
someone who opted out, and silence to someone expecting a call tomorrow. The
first two are why every run checks Close before drafting. The third is why a
booked lead is never held for a question about their record.

---

Bring one of these, filled in for one job in your business, and the build
conversation is the short one.
