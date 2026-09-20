# Webhook endpoints

Each endpoint is a URL the agent listens on. The prompt is what the agent is told when an event lands. Secrets and endpoint ids are not part of the export; they are issued when you create the endpoint.

## Vapi - Brand B agent

```text
Analyze the call and determine what needs to be done and update the CRM as needed.  Post a summary to #leads in Slack
```

## Instantly v3

```text
Decide what to do from the instantly AI lead event.
```

## Cal.com

```text
Determine what to do for this Cal.com booking event. Verify the booking via cal-com before acting.
```

## Close CRM (via relay)

```text
Determine what to do for this Close CRM lead event. Look the lead up in Close by id before acting.
```
