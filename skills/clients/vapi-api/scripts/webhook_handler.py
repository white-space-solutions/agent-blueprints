#!/usr/bin/env python3
"""
Process a VAPI webhook event payload and output structured data for the agent.

Usage:
  python3 webhook_handler.py <event_json_file>

The agent calls this after receiving a VAPI webhook event. The script parses
the event and outputs a structured JSON summary that the agent can use to:
  - Log call outcomes to Close CRM
  - Update lead status
  - Flag calls that need Alex's attention
  - Trigger follow-up actions

Event types handled:
  - status-update: Call status changed (ringing, in-progress, ended, etc.)
  - end-of-call-report: Call completed with summary/transcript/analysis
  - transcript: Real-time transcript snippet
  - hang: Assistant failed to respond
"""

import json
import sys
import os
from datetime import datetime, timezone


def parse_event(payload):
    message = payload.get("message", {})
    msg_type = message.get("type", "unknown")
    call = message.get("call", {})

    base = {
        "event_type": msg_type,
        "call_id": call.get("id", "unknown"),
        "timestamp": payload.get("timestamp", datetime.now(timezone.utc).isoformat()),
        "customer_number": None,
        "customer_name": None,
        "call_status": call.get("status", "unknown"),
    }

    # Extract customer info
    customer = call.get("customer", {})
    if customer:
        base["customer_number"] = customer.get("number")
        base["customer_name"] = customer.get("name")

    # Extract phone number info
    phone_number = payload.get("phoneNumber", {})
    if phone_number:
        base["from_number"] = phone_number.get("number")
        base["phone_number_id"] = phone_number.get("id")

    if msg_type == "status-update":
        base["new_status"] = message.get("status", "unknown")
        base["requires_action"] = False
        base["action_note"] = f"Call {base['call_id']} status: {base['new_status']}"

    elif msg_type == "end-of-call-report":
        ended_reason = message.get("endedReason", "unknown")
        base["ended_reason"] = ended_reason

        # Extract summary/analysis
        analysis = message.get("analysis", {})
        summary = analysis.get("summary", "")
        success_eval = analysis.get("successEvaluation", "")

        base["call_summary"] = summary
        base["success_evaluation"] = success_eval

        # Extract transcript if available
        artifact = message.get("artifact", {})
        transcript = artifact.get("transcript", "")
        messages = artifact.get("messages", [])

        base["has_transcript"] = bool(transcript)
        base["message_count"] = len(messages)

        # Determine if this needs human follow-up
        base["requires_action"] = False
        action_note = "Call completed."

        # Check for interest signals in summary
        interest_keywords = ["interested", "demo", "call back", "schedule", "follow up",
                             "learn more", "tell me more", "sounds good", "pricing", "quote"]
        if summary:
            summary_lower = summary.lower()
            if any(kw in summary_lower for kw in interest_keywords):
                base["requires_action"] = True
                action_note = (
                    f"INTEREST SIGNAL: Call to {base.get('customer_number', '?')} showed interest. "
                    f"Summary: {summary[:200]}"
                )

        # Check for negative outcomes
        negative_keywords = ["not interested", "do not call", "remove", "stop calling",
                             "wrong number", "don't call"]
        if summary:
            summary_lower = summary.lower()
            if any(kw in summary_lower for kw in negative_keywords):
                base["requires_action"] = True
                base["negative_outcome"] = True
                action_note = (
                    f"NEGATIVE OUTCOME: {base.get('customer_number', '?')}. "
                    f"Summary: {summary[:200]}"
                )

        # Check ended reasons that indicate problems
        if ended_reason in ["assistant-error", "silence-timed-out", "pipeline-error"]:
            base["requires_action"] = True
            action_note = f"Call ended with problem: {ended_reason}"

        base["action_note"] = action_note

        # Serialize transcript messages separately for agent to use
        base["transcript_messages"] = messages

    elif msg_type == "transcript":
        base["role"] = message.get("role", "unknown")
        base["transcript_type"] = message.get("transcriptType", "unknown")
        base["transcript_text"] = message.get("transcript", "")
        base["requires_action"] = False

    elif msg_type == "hang":
        base["requires_action"] = True
        base["action_note"] = (
            f"HANG: Assistant failed to respond on call {base['call_id']} "
            f"to {base.get('customer_number', '?')}"
        )

    else:
        base["requires_action"] = False
        base["action_note"] = f"Received {msg_type} event for call {base['call_id']}"

    return base


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: webhook_handler.py <event_json_file>"}))
        sys.exit(1)

    filepath = sys.argv[1]
    with open(filepath, "r") as f:
        payload = json.load(f)

    result = parse_event(payload)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
