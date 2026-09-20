# Sequence copy, normalized

A working subset of the copy the agent sends, with the specifics pulled out
into slots so it reads for any business. The full document carries copy for
every touch in every sequence, plus a 36-email long-term nurture series; this
is enough to see the pattern and write your own.

Slots: `{{ first_name }}` the lead, `{{ sender }}` the owner's first name,
`[brand]`, `[service]` what you sell, `[booking link]`, `[time A]` and
`[time B]` two real slots read from live availability, never invented.

Rules that apply to all of it: every touch adds something, no bare bumps,
no em dashes, no AI-speak, one channel per day, and the ask is always low
pressure. Read `../../skills/doctrine/email-copywriting/SKILL.md` and
`sms-copywriting` for the voice rules these were written against.

## Sequence 3: Get-Booked

Day 0 email, propose times.

```text
Subject: Let's map your next [outcome]

Hi {{ first_name }},

Glad [what they said is working] is bringing in results. Sounds like the
bottleneck is [volume / follow-up / capacity], not demand.

If you want, we can walk through what you're running now and show what
[service] would look like at your volume. Any of these work: [time A] or
[time B]. If not, grab whatever is easiest here: [booking link].

Best,
{{ sender }}
```

Day 2 email, add a proof point. Send only if no reply.

```text
Subject: The gap most [people like them] skip

Hi {{ first_name }},

One thing I meant to flag: most [people like them] are one step away from
[the specific result]. The difference between [the common way] and [your
way] is the single biggest lever, bigger than [the thing they obsess over].

Happy to show you what that looks like on the numbers. [booking link] if you
want to map it out.

Best,
{{ sender }}
```

SMS, alternating days with the emails.

```text
Day 1:  {{ first_name }}, {{ sender }} here. You asked about [topic] on
        [brand]. What are you working on right now? Reply STOP to opt out.
Day 4:  Quick one: are you doing [the thing] today, or is this something
        you're just starting to look at? Changes what I'd send you.
Day 10: Got two slots open this week if it's easier to just talk it through.
        [time A] or [time B] work?
Day 21: Last one from me unless you want to pick it up. If timing's wrong
        just say so and I'll leave you alone.
```

Day 30 is a clean breakup email, then the lead moves to long-term nurture.

## Sequence 4: Exploration

Day 0, the diagnostic. Ask, then route. No booking link yet.

```text
Subject: Quick question on where you're at

Hi {{ first_name }},

Thanks for the note. To point you in the right direction, can I ask what
you're running today and what you're trying to solve? Are you doing [the
thing] at all right now, and [the one volume question that tells you fit]?

Depending on the answer, what fits could be very different, so I'd rather
not guess.

Best,
{{ sender }}
```

Disqualify or wrong fit, honest.

```text
Subject: Correcting myself

Hi {{ first_name }},

Sounds like what you're after isn't [service], and I want to make sure I'm
not wasting your time. We don't do [the thing they asked for]. What we do
is [one plain sentence].

If that's not you, no hard feelings, and I'll stop emailing.

Best,
{{ sender }}
```

## Sequence 5: Re-Booking

Within minutes of a no-show or cancellation. Casual, not accusatory.

```text
Subject: Missed you, want to grab a new time?

Hi {{ first_name }},

Looks like we missed each other today, no worries. If the timing went
sideways, happy to find something that actually works.

[time A] or [time B] are open this week, or grab whatever is easiest here:
[booking link].

Best,
{{ sender }}
```

```text
SMS, within 5 minutes:  {{ first_name }}, looks like we missed each other.
                        No problem. Want me to find another time?
SMS, day 2 if silent:   [time A] or [time B] are open. Either work, or grab
                        whatever's easiest: [booking link]
```

Two no-shows: breakup note, stop.

## Sequence 6: Post-Call Nurture

Weekly, when you owe them something specific.

```text
Subject: The [thing] I promised

Hi {{ first_name }},

Following up from our call, here's the [thing] I mentioned. It shows
[the one insight it gives them].

If you want, send me [their input] and I'll run it for you before we talk
again.

Best,
{{ sender }}
```

Monthly, when the timing is theirs.

```text
Subject: Worth a look when you're back at it

Hi {{ first_name }},

No rush on this. When you're closer to [the decision], the math worth a
look is [the metric] against [the other metric]. That's usually where
[the result] hides.

Happy to run your numbers whenever it's convenient.

Best,
{{ sender }}
```

## Sequence 7: Long-Term Nurture (one of 36)

The rule for this whole series: give away the real thing. The exact method,
the real numbers, the actual vendor links. Someone who could run it
themselves off your email is exactly the person who hires you to run it.
The ask is a rotating soft P.S., never the subject.

Email 1, day 0, new thread.

```text
Subject: our [method] equation
Preview: the [split] we run every [engagement] against

Hi {{ first_name }},

Every [engagement] we run breaks down to three levers, weighted like this.
Steal it.

[50%] is [lever one]. [Two sentences on what it actually means and why
most of the result is decided here.]

[30%] is [lever two]. [Two sentences.]

[20%] is [lever three]. [Two sentences, ending on why one or two attempts
is not a real try.]

Most [people like them] invert this. They obsess over [the visible part]
while ignoring [the lever that matters]. That's backwards, and it's the
single most common reason [the method] "doesn't work."

Over the next couple of weeks I'll break down each lever with the exact way
we run it.

{{ sender }}

P.S. If you want, reply with [their context] and I'll tell you which lever
is most likely leaking for you.
```

Cadence for the series: every 2 to 3 days for weeks 0 to 3, weekly for
weeks 4 to 6, biweekly then monthly through month 12 and beyond. Email
only. Only a booking, a reply, or an opt-out ends it.

## Sequence 8: Proposal Follow-Through

Day 21, the honest ask. The agent owns the rhythm, never the negotiation:
no price, discount, term or scope ever goes out from it.

```text
Subject: where'd we land

Hi {{ first_name }},

Following up on the proposal from [date]. I'd rather have a clean no than
leave it open, so whichever way you're leaning is fine by me.

If it's a yes, I'll send it for signature and get the invoice over the same
day. If it's a no or a not-yet, tell me and I'll stop chasing and just send
you useful stuff occasionally.

Best,
{{ sender }}
```
