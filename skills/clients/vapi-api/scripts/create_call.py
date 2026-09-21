#!/usr/bin/env python3
"""
Create an outbound call via the VAPI API.

Usage:
  python3 create_call.py --to <phone> --assistant-id <id> [--phone-number-id <id>] [--first-message <msg>]

Environment:
  VAPI_API_KEY    - VAPI private API key (Bearer token)
  VAPI_BASE_URL   - API base URL (default: https://api.vapi.ai)

Returns JSON with the created call object.
"""

import os
import sys
import json
import argparse
import urllib.request
import urllib.error

BASE_URL = os.environ.get("VAPI_BASE_URL", "https://api.vapi.ai")


def make_request(method, path, body=None):
    url = f"{BASE_URL}{path}"
    headers = {
        "Authorization": f"Bearer {os.environ['VAPI_API_KEY']}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    }

    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print(json.dumps({"error": f"HTTP {e.code}", "detail": error_body}), file=sys.stderr)
        sys.exit(1)


def create_call(customer_number, assistant_id=None, phone_number_id=None,
                first_message=None, assistant_config=None, squad_id=None):
    """
    Create an outbound phone call via VAPI.
    
    customer_number: E.164 format, e.g. "+14155552671"
    assistant_id: Saved assistant ID (or use assistant_config for transient)
    phone_number_id: VAPI phone number ID to call from
    first_message: Override the assistant's first message
    assistant_config: Dict with transient assistant config (model, voice, messages, etc.)
    squad_id: Squad ID instead of assistant_id
    """
    body = {
        "customer": {
            "number": customer_number
        }
    }

    if assistant_id:
        body["assistantId"] = assistant_id
    if phone_number_id:
        body["phoneNumberId"] = phone_number_id
    if assistant_config:
        body["assistant"] = assistant_config
    if first_message and "assistant" in body:
        body["assistant"]["firstMessage"] = first_message
    if squad_id:
        body["squadId"] = squad_id

    return make_request("POST", "/call", body)


def main():
    parser = argparse.ArgumentParser(description="Create an outbound VAPI call")
    parser.add_argument("--to", required=True, help="Customer phone number (E.164)")
    parser.add_argument("--assistant-id", help="Saved assistant ID")
    parser.add_argument("--phone-number-id", help="VAPI phone number ID to call from")
    parser.add_argument("--first-message", help="Override first message")
    parser.add_argument("--squad-id", help="Squad ID")
    parser.add_argument("--customer-name", help="Customer name for personalization")
    parser.add_argument("--context", help="JSON string with additional call context/metadata")
    args = parser.parse_args()

    if not os.environ.get("VAPI_API_KEY"):
        print(json.dumps({"error": "VAPI_API_KEY environment variable not set"}))
        sys.exit(1)

    assistant_config = None
    if args.first_message and not args.assistant_id:
        # If no saved assistant, build a minimal transient config
        assistant_config = {
            "firstMessage": args.first_message,
            "model": {
                "provider": "openai",
                "model": "gpt-4.1",
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a follow-up voice assistant for a services company "
                            "(Brand A / Brand B). You're calling to follow up on an email "
                            "conversation. Be conversational, brief, and respectful of their time. "
                            "If they express interest in a demo or more information, note it. "
                            "If they're not interested, thank them and end the call gracefully."
                        )
                    }
                ]
            },
            "voice": {"provider": "vapi", "voiceId": "Elliot", "version": 2},
            "transcriber": {"provider": "deepgram", "model": "nova-3", "language": "en"},
        }

    result = create_call(
        customer_number=args.to,
        assistant_id=args.assistant_id,
        phone_number_id=args.phone_number_id,
        first_message=args.first_message if args.assistant_id else None,
        assistant_config=assistant_config,
        squad_id=args.squad_id,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
