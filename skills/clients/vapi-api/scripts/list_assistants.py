#!/usr/bin/env python3
"""
List VAPI assistants (phone and chat agents), or fetch one by ID.

Usage:
  python3 list_assistants.py [--limit 25]
  python3 list_assistants.py --id assistant_abc123

Returns JSON. Without --id, returns the assistants array. With --id, returns
the single assistant object.

This closes the "visibility into my phone and chat agents" gap: VAPI's MCP
server exposes list_assistants / get_assistant, and this script reproduces
that surface over the REST API.

Endpoints:
  GET {BASE_URL}/assistant?limit=N
  GET {BASE_URL}/assistant/{id}
"""

import os
import sys
import json
import argparse
import urllib.request
import urllib.error
import urllib.parse

BASE_URL = os.environ.get("VAPI_BASE_URL", "https://api.vapi.ai")


def _auth_header():
    key = os.environ.get("VAPI_API_KEY")
    if not key:
        print(json.dumps({"error": "VAPI_API_KEY environment variable not set"}))
        sys.exit(1)
    return {
        "Authorization": f"Bearer {key}",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    }


def main():
    parser = argparse.ArgumentParser(description="List or fetch VAPI assistants")
    parser.add_argument("--limit", type=int, default=25, help="Max results (ignored with --id)")
    parser.add_argument("--id", help="Fetch a single assistant by ID")
    args = parser.parse_args()

    if args.id:
        url = f"{BASE_URL}/assistant/{args.id}"
    else:
        query = urllib.parse.urlencode({"limit": args.limit})
        url = f"{BASE_URL}/assistant?{query}"

    req = urllib.request.Request(url, headers=_auth_header())

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
