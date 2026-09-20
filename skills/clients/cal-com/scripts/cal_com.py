#!/usr/bin/env python3
"""
Cal.com API v2 CLI — stdlib-only Python 3 script for calendar operations.

Auth:  Bearer token — API key prefixed with cal_
Base:  https://api.cal.com/v2/

Usage:
    export CAL_API_KEY=cal_live_...
    python cal_com.py list-event-types --username <your-cal-handle>
    python cal_com.py get-availability --event-type-id 123 --start 2026-08-16 --end 2026-08-23
    python cal_com.py get-availability --event-type-slug direct-mail-consult --username <your-cal-handle> --start 2026-08-16 --end 2026-08-23
    python cal_com.py create-booking --event-type-id 123 --start "2026-08-18T14:00:00Z" --attendee-name "John" --attendee-email "john@example.com" --timezone "America/New_York"
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from typing import Optional


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = "https://api.cal.com/v2/"


def _get_api_key() -> str:
    key = os.environ.get("CAL_API_KEY", "")
    if not key:
        _die("CAL_API_KEY environment variable is required", status=2)
    return key


def _auth_header(key: str) -> str:
    return f"Bearer {key}"


def _die(msg: str, status: int = 1) -> None:
    print(json.dumps({"error": msg, "status": status}), file=sys.stderr)
    sys.exit(status)


def _out(obj) -> None:
    """Write JSON to stdout."""
    json.dump(obj, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _request(
    method: str,
    path: str,
    params: Optional[dict] = None,
    body: Optional[dict] = None,
    extra_headers: Optional[dict] = None,
    max_retries: int = 4,
) -> dict:
    """Make an authenticated JSON request to the Cal.com API v2."""
    api_key = _get_api_key()
    auth = _auth_header(api_key)

    url = f"{BASE_URL}{path}"
    if params:
        url = f"{url}?{urllib.parse.urlencode(params, doseq=True)}"

    data = json.dumps(body).encode("utf-8") if body is not None else None

    headers = {
        "Authorization": auth,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    }
    if extra_headers:
        headers.update(extra_headers)

    attempt = 0
    backoff = 1.0

    while True:
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req) as resp:
                raw = resp.read()
                return json.loads(raw) if raw else {}

        except urllib.error.HTTPError as exc:
            status = exc.code
            raw_body = exc.read()

            if status == 429 and attempt < max_retries:
                retry_after = exc.headers.get("Retry-After") or exc.headers.get("retry-after") or ""
                try:
                    wait = float(retry_after)
                except ValueError:
                    wait = backoff
                wait = max(wait, 0.5)
                sys.stderr.write(f"[cal-com] 429 rate limited — waiting {wait:.1f}s (attempt {attempt+1})\n")
                time.sleep(wait)
                attempt += 1
                backoff = min(backoff * 2, 30)
                continue

            if status >= 500 and attempt < max_retries:
                sys.stderr.write(f"[cal-com] {status} server error — retrying in {backoff:.1f}s (attempt {attempt+1})\n")
                time.sleep(backoff)
                attempt += 1
                backoff = min(backoff * 2, 30)
                continue

            try:
                err_body = json.loads(raw_body)
            except Exception:
                err_body = raw_body.decode("utf-8", errors="replace")

            _die(f"HTTP {status}: {err_body}", status=status)

        except urllib.error.URLError as exc:
            _die(f"Network error: {exc.reason}", status=1)


# ---------------------------------------------------------------------------
# Subcommand implementations
# ---------------------------------------------------------------------------


def cmd_list_event_types(args) -> None:
    """List all event types for a given username.

    GET /v2/event-types?username=X
    cal-api-version: 2024-06-14
    """
    params = {}
    if args.username:
        params["username"] = args.username
    if args.usernames:
        params["usernames"] = args.usernames
    if args.event_slug:
        params["eventSlug"] = args.event_slug
    if args.org_slug:
        params["orgSlug"] = args.org_slug

    result = _request(
        "GET",
        "event-types",
        params=params,
        extra_headers={"cal-api-version": "2024-06-14"},
    )

    # Simplify output — surface id, slug, title, length, and scheduling type
    event_types = result.get("data", [])
    simplified = []
    for et in event_types:
        simplified.append({
            "id": et.get("id"),
            "slug": et.get("slug"),
            "title": et.get("title"),
            "lengthInMinutes": et.get("lengthInMinutes"),
            "description": (et.get("description") or "")[:120],
            "hidden": et.get("hidden", False),
        })
    _out({"count": len(simplified), "eventTypes": simplified})


def cmd_get_availability(args) -> None:
    """Get available time slots for an event type.

    GET /v2/slots/available?eventTypeId=X&start=T&end=T
    cal-api-version: 2024-09-04

    Supports both eventTypeId directly or resolving by slug+username.
    """
    params = {
        "start": _ensure_iso(args.start),
        "end": _ensure_iso(args.end),
    }

    if args.event_type_id:
        params["eventTypeId"] = args.event_type_id
    elif args.event_type_slug:
        # Resolve slug → event type ID
        resolve_params = {"username": args.username, "eventSlug": args.event_type_slug}
        if args.org_slug:
            resolve_params["orgSlug"] = args.org_slug

        resolved = _request(
            "GET",
            "event-types",
            params=resolve_params,
            extra_headers={"cal-api-version": "2024-06-14"},
        )
        event_types = resolved.get("data", [])
        if not event_types:
            _die(f"No event type found with slug '{args.event_type_slug}' for username '{args.username}'")
        eid = event_types[0]["id"]
        params["eventTypeId"] = eid
    else:
        _die("Either --event-type-id or --event-type-slug (with --username) is required")

    if args.duration:
        params["duration"] = args.duration
    if args.timezone:
        params["timeZone"] = args.timezone

    result = _request(
        "GET",
        "slots/available",
        params=params,
        extra_headers={"cal-api-version": "2024-09-04"},
    )

    # Flatten into a simple list for the agent to reason over
    data = result.get("data", {})
    slots = []
    for date_str, day_slots in sorted(data.items()):
        for s in day_slots:
            if isinstance(s, dict):
                slots.append({
                    "date": date_str,
                    "start": s.get("start"),
                    "end": s.get("end"),
                })
            else:
                slots.append({
                    "date": date_str,
                    "start": s,
                })

    _out({"count": len(slots), "slots": slots, "eventTypeId": params.get("eventTypeId")})


def cmd_create_booking(args) -> None:
    """Create a booking for an event type.

    POST /v2/bookings
    cal-api-version: 2026-02-25

    Requires eventTypeId and a UTC start time.
    """
    body = {
        "start": _ensure_utc_iso(args.start),
        "attendee": {
            "name": args.attendee_name,
            "email": args.attendee_email,
            "timeZone": args.timezone or "America/New_York",
        },
    }

    if args.event_type_id:
        body["eventTypeId"] = args.event_type_id
    elif args.event_type_slug and args.username:
        # Resolve slug → ID
        resolve_params = {"username": args.username, "eventSlug": args.event_type_slug}
        if args.org_slug:
            resolve_params["orgSlug"] = args.org_slug

        resolved = _request(
            "GET",
            "event-types",
            params=resolve_params,
            extra_headers={"cal-api-version": "2024-06-14"},
        )
        event_types = resolved.get("data", [])
        if not event_types:
            _die(f"No event type found with slug '{args.event_type_slug}' for username '{args.username}'")
        body["eventTypeId"] = event_types[0]["id"]
        body["username"] = args.username
    else:
        _die("Either --event-type-id or (--event-type-slug + --username) is required")

    if args.attendee_phone:
        body["attendee"]["phoneNumber"] = args.attendee_phone

    if args.metadata:
        try:
            body["metadata"] = json.loads(args.metadata)
        except json.JSONDecodeError as exc:
            _die(f"Invalid JSON in --metadata: {exc}")

    result = _request(
        "POST",
        "bookings",
        body=body,
        extra_headers={"cal-api-version": "2026-02-25"},
    )

    booking = result.get("data", result)
    _out({
        "bookingUid": booking.get("uid"),
        "status": booking.get("status"),
        "start": booking.get("start"),
        "end": booking.get("end"),
        "attendee": booking.get("attendees", [{}])[0].get("email") if booking.get("attendees") else None,
        "meetingUrl": booking.get("location"),
        "cancelUrl": booking.get("cancellationUrl"),
    })


def cmd_list_bookings(args) -> None:
    """List bookings from Cal.com, optionally filtered by status and date range.

    GET /v2/bookings?status=X&afterStart=T&beforeEnd=T
    cal-api-version: 2026-05-01

    Use this for booking tracking: pull recent upcoming/past bookings and cross-check
    against Close CRM to catch no-shows, confirmations, and cancellations.
    """
    params = {"limit": args.limit or 50}

    # Status filter: upcoming, past, cancelled, recurring, unconfirmed
    statuses = []
    if args.status:
        statuses = [s.strip() for s in args.status.split(",")]
    else:
        statuses = ["upcoming", "past"]  # default: both

    all_bookings = []
    event_type_ids = None

    # Resolve event type slugs if provided
    if args.event_type_slugs and args.username:
        resolve_params = {"username": args.username}
        resolved = _request(
            "GET", "event-types", params=resolve_params,
            extra_headers={"cal-api-version": "2024-06-14"},
        )
        event_types = resolved.get("data", [])
        slug_set = set(s.strip() for s in args.event_type_slugs.split(","))
        event_type_ids = [et["id"] for et in event_types if et.get("slug") in slug_set]
        if event_type_ids:
            params["eventTypeIds"] = ",".join(str(eid) for eid in event_type_ids)

    if args.after_start:
        params["afterStart"] = args.after_start
    if args.before_end:
        params["beforeEnd"] = args.before_end
    if args.attendee_email:
        params["attendeeEmail"] = args.attendee_email

    # Fetch each status separately (API requires one at a time) and merge
    for status in statuses:
        p = dict(params)
        p["status"] = status
        p["limit"] = min(args.limit or 50, 50)

        page_count = 0
        max_pages = args.max_pages or 5
        while page_count < max_pages:
            result = _request(
                "GET", "bookings", params=p,
                extra_headers={"cal-api-version": "2026-05-01"},
            )
            batch = result.get("data", [])
            for b in batch:
                all_bookings.append({
                    "uid": b.get("uid"),
                    "status": b.get("status"),
                    "title": b.get("title"),
                    "start": b.get("start"),
                    "end": b.get("end"),
                    "attendees": [
                        {"name": a.get("name"), "email": a.get("email"),
                         "phoneNumber": a.get("phoneNumber"), "noShow": a.get("noShow"),
                         "timeZone": a.get("timeZone")}
                        for a in (b.get("attendees") or [])
                    ],
                    "location": b.get("location"),
                    "cancellationReason": b.get("cancellationReason"),
                    "createdAt": b.get("createdAt"),
                    "updatedAt": b.get("updatedAt"),
                    "eventTypeId": b.get("eventTypeId"),
                    "metadata": b.get("metadata"),
                })

            pagination = result.get("pagination", {})
            cursor = pagination.get("nextCursor")
            if not cursor or pagination.get("hasMore") is False:
                break
            p["cursor"] = cursor
            page_count += 1

    _out({"count": len(all_bookings), "statuses": statuses, "bookings": all_bookings})


def cmd_get_event_type(args) -> None:
    """Get a single event type by ID.

    GET /v2/event-types/{id}
    """
    result = _request(
        "GET",
        f"event-types/{args.event_type_id}",
        extra_headers={"cal-api-version": "2024-06-14"},
    )
    et = result.get("data", result)
    _out({
        "id": et.get("id"),
        "slug": et.get("slug"),
        "title": et.get("title"),
        "lengthInMinutes": et.get("lengthInMinutes"),
        "description": et.get("description"),
        "hidden": et.get("hidden", False),
        "bookingUrl": et.get("bookingUrl"),
    })


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def _ensure_iso(val: str) -> str:
    """If val is a bare date (YYYY-MM-DD), extend to start/end of day as appropriate."""
    if "T" in val:
        return val
    # Bare date — caller should have already set start/end appropriately
    return val


def _ensure_utc_iso(val: str) -> str:
    """Ensure the value is a full UTC ISO 8601 string."""
    if "T" in val:
        if val.endswith("Z") or "+" in val or val.count("-") > 2:
            return val
        return val + "Z"
    return val + "T00:00:00Z"


# ---------------------------------------------------------------------------
# CLI wiring
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cal_com",
        description="Cal.com API v2 CLI — reads CAL_API_KEY from environment, outputs JSON to stdout.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # list-event-types
    p = sub.add_parser("list-event-types", help="List event types for a username.")
    p.add_argument("--username", default=None, help="Cal.com username (e.g., <your-cal-handle>).")
    p.add_argument("--usernames", default=None, help="Comma-separated usernames for dynamic events.")
    p.add_argument("--event-slug", default=None, dest="event_slug", help="Filter by event type slug.")
    p.add_argument("--org-slug", default=None, dest="org_slug", help="Organization slug if applicable.")
    p.set_defaults(func=cmd_list_event_types)

    # get-availability
    p = sub.add_parser("get-availability", help="Get available slots for an event type.")
    p.add_argument("--event-type-id", type=int, default=None, dest="event_type_id", help="Event type ID.")
    p.add_argument("--event-type-slug", default=None, dest="event_type_slug", help="Event type slug (requires --username).")
    p.add_argument("--username", default=None, help="Username (required with --event-type-slug).")
    p.add_argument("--org-slug", default=None, dest="org_slug", help="Organization slug.")
    p.add_argument("--start", required=True, help="UTC start of window (ISO 8601, e.g. 2026-08-16 or 2026-08-16T00:00:00Z).")
    p.add_argument("--end", required=True, help="UTC end of window (ISO 8601).")
    p.add_argument("--duration", type=int, default=None, help="Slot duration in minutes.")
    p.add_argument("--timezone", default=None, help="Return slots in this timezone (e.g., America/New_York).")
    p.set_defaults(func=cmd_get_availability)

    # create-booking
    p = sub.add_parser("create-booking", help="Create a booking.")
    p.add_argument("--event-type-id", type=int, default=None, dest="event_type_id", help="Event type ID.")
    p.add_argument("--event-type-slug", default=None, dest="event_type_slug", help="Event type slug (requires --username).")
    p.add_argument("--username", default=None, help="Username (required with --event-type-slug).")
    p.add_argument("--org-slug", default=None, dest="org_slug", help="Organization slug.")
    p.add_argument("--start", required=True, help="UTC start time (ISO 8601, e.g. 2026-08-18T14:00:00Z).")
    p.add_argument("--attendee-name", required=True, dest="attendee_name", help="Attendee full name.")
    p.add_argument("--attendee-email", required=True, dest="attendee_email", help="Attendee email.")
    p.add_argument("--attendee-phone", default=None, dest="attendee_phone", help="Attendee phone (E.164).")
    p.add_argument("--timezone", default="America/New_York", help="Attendee timezone (default: America/New_York).")
    p.add_argument("--metadata", default=None, help="JSON string of metadata key-value pairs.")
    p.set_defaults(func=cmd_create_booking)

    # list-bookings
    p = sub.add_parser("list-bookings", help="List bookings, optionally filtered by status and date range.")
    p.add_argument("--status", default=None, help="Comma-separated statuses: upcoming,past,cancelled,recurring,unconfirmed. Default: upcoming,past")
    p.add_argument("--after-start", default=None, dest="after_start", help="ISO 8601 lower bound on start time.")
    p.add_argument("--before-end", default=None, dest="before_end", help="ISO 8601 upper bound on end time.")
    p.add_argument("--attendee-email", default=None, dest="attendee_email", help="Filter by attendee email.")
    p.add_argument("--event-type-slugs", default=None, dest="event_type_slugs", help="Comma-separated slugs (requires --username).")
    p.add_argument("--username", default=None, help="Username (required with --event-type-slugs).")
    p.add_argument("--limit", type=int, default=50, help="Max bookings per status per page (default 50).")
    p.add_argument("--max-pages", type=int, default=5, dest="max_pages", help="Max pages per status (default 5).")
    p.set_defaults(func=cmd_list_bookings)

    # get-event-type
    p = sub.add_parser("get-event-type", help="Get a single event type by ID.")
    p.add_argument("--event-type-id", type=int, required=True, dest="event_type_id", help="Event type ID.")
    p.set_defaults(func=cmd_get_event_type)

    return parser


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)
