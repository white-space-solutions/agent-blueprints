#!/usr/bin/env python3
"""
Get a VAPI call by ID.

Usage:
  python3 get_call.py <call_id>

Returns JSON with the call object including status, transcript, artifacts, etc.
"""

import os
import sys
import json
import urllib.request
import urllib.error

BASE_URL = os.environ.get("VAPI_BASE_URL", "https://api.vapi.ai")


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: get_call.py <call_id>"}))
        sys.exit(1)

    call_id = sys.argv[1]

    if not os.environ.get("VAPI_API_KEY"):
        print(json.dumps({"error": "VAPI_API_KEY environment variable not set"}))
        sys.exit(1)

    url = f"{BASE_URL}/call/{call_id}"
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
