#!/usr/bin/env python3
"""
List VAPI calls, optionally filtered.

Usage:
  python3 list_calls.py [--limit 10] [--assistant-id <id>] [--status ended]

Returns JSON array of call objects.
"""

import os
import sys
import json
import argparse
import urllib.request
import urllib.error
import urllib.parse

BASE_URL = os.environ.get("VAPI_BASE_URL", "https://api.vapi.ai")


def main():
    parser = argparse.ArgumentParser(description="List VAPI calls")
    parser.add_argument("--limit", type=int, default=10, help="Max results")
    parser.add_argument("--assistant-id", help="Filter by assistant ID")
    parser.add_argument("--status", help="Filter by call status")
    args = parser.parse_args()

    if not os.environ.get("VAPI_API_KEY"):
        print(json.dumps({"error": "VAPI_API_KEY environment variable not set"}))
        sys.exit(1)

    params = {"limit": args.limit}
    if args.assistant_id:
        params["assistantId"] = args.assistant_id
    if args.status:
        params["status"] = args.status

    query = urllib.parse.urlencode(params)
    url = f"{BASE_URL}/call?{query}"

    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {os.environ['VAPI_API_KEY']}",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    })

    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
            print(json.dumps(result, indent=2))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print(json.dumps({"error": f"HTTP {e.code}", "detail": error_body}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
