#!/usr/bin/env python3
"""
Close CRM CLI — stdlib-only Python 3 script for lead management.

Auth:  HTTP Basic Auth — API key as username, empty password.
       Header: Authorization: Basic base64("APIKEY:")
Base:  https://api.close.com/api/v1/

Usage:
    export CLOSE_API_KEY=sk_prod_...
    python close_crm.py find-lead --email alice@example.com
    python close_crm.py lead-history --id lead_XXX --limit 25
    python close_crm.py last-touch --id lead_XXX
    python close_crm.py create-note --lead-id lead_XXX --text "Called, left VM"
    python close_crm.py list-pipelines
    python close_crm.py set-opportunity-stage --opportunity-id oppo_XXX --status-id stat_YYY
    python close_crm.py create-opportunity --lead-id lead_XXX --status-id stat_YYY --value 5000
    python close_crm.py list-sequences
    python close_crm.py enroll-sequence --sequence-id seq_XXX --contact-id cont_YYY \
                                         --lead-id lead_ZZZ --email-account-id emailacct_WWW
    python close_crm.py search --query '{"query":{"type":"and","queries":[...]}}'
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Optional


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = "https://api.close.com/api/v1"


def _get_api_key() -> str:
    key = os.environ.get("CLOSE_API_KEY", "")
    if not key:
        _die("CLOSE_API_KEY environment variable is not set.", status=1)
    return key


def _auth_header(api_key: str) -> str:
    """Return the Authorization header value for HTTP Basic Auth.

    Close uses API key as username and empty string as password.
    The encoded credential is base64("APIKEY:") — note the trailing colon.
    """
    credentials = f"{api_key}:"
    encoded = base64.b64encode(credentials.encode("utf-8")).decode("ascii")
    return f"Basic {encoded}"


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------

def _request(
    method: str,
    path: str,
    params: Optional[dict] = None,
    body: Optional[dict] = None,
    max_retries: int = 4,
) -> dict:
    """Make an authenticated JSON request to the Close API.

    Handles:
    - Basic Auth header construction
    - Query string encoding
    - JSON serialisation / deserialisation
    - 429 / 5xx retry with exponential back-off (honours RateLimit reset header)
    - Surfaces HTTP error bodies as structured errors
    """
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
    }

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

            # Parse rate-limit reset from RateLimit header (e.g. "limit=100, remaining=0, reset=4.2")
            rate_header = exc.headers.get("RateLimit") or exc.headers.get("ratelimit") or ""
            retry_after_raw = exc.headers.get("Retry-After") or exc.headers.get("retry-after") or ""

            reset_secs = None
            for part in rate_header.split(","):
                part = part.strip()
                if part.startswith("reset="):
                    try:
                        reset_secs = float(part.split("=", 1)[1])
                    except ValueError:
                        pass

            if reset_secs is None and retry_after_raw:
                try:
                    reset_secs = float(retry_after_raw)
                except ValueError:
                    pass

            if status == 429 and attempt < max_retries:
                wait = reset_secs if reset_secs is not None else backoff
                wait = max(wait, 0.5)
                sys.stderr.write(f"[close_crm] 429 rate limited — waiting {wait:.1f}s (attempt {attempt+1})\n")
                time.sleep(wait)
                attempt += 1
                backoff = min(backoff * 2, 30)
                continue

            if status >= 500 and attempt < max_retries:
                sys.stderr.write(f"[close_crm] {status} server error — retrying in {backoff:.1f}s (attempt {attempt+1})\n")
                time.sleep(backoff)
                attempt += 1
                backoff = min(backoff * 2, 30)
                continue

            # Parse error body
            try:
                err_body = json.loads(raw_body)
            except Exception:
                err_body = raw_body.decode("utf-8", errors="replace")

            _die(f"HTTP {status}: {err_body}", status=status)

        except urllib.error.URLError as exc:
            _die(f"Network error: {exc.reason}", status=1)


def _paginate_offset(path: str, params: Optional[dict] = None, limit: int = 100) -> list:
    """Collect all pages from an offset-paginated endpoint (has_more / _skip)."""
    results = []
    skip = 0
    p = dict(params or {})
    p["_limit"] = limit

    while True:
        p["_skip"] = skip
        page = _request("GET", path, params=p)
        data = page.get("data", [])
        results.extend(data)
        if not page.get("has_more", False):
            break
        skip += len(data)
        if not data:
            break
    return results


# ---------------------------------------------------------------------------
# Error / output helpers
# ---------------------------------------------------------------------------

def _die(msg: str, status: int = 1) -> None:
    print(json.dumps({"error": msg, "status": status}), file=sys.stderr)
    sys.exit(status)


def _out(obj) -> None:
    print(json.dumps(obj, indent=2, default=str))


# ---------------------------------------------------------------------------
# Timestamp utilities
# ---------------------------------------------------------------------------

def _parse_ts(ts_str: Optional[str]) -> Optional[datetime]:
    if not ts_str:
        return None
    # Close returns ISO 8601 with or without timezone
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%f+00:00",
        "%Y-%m-%dT%H:%M:%S+00:00",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
    ):
        try:
            dt = datetime.strptime(ts_str[:26], fmt[:len(fmt)])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


def _days_ago(dt: Optional[datetime]) -> Optional[int]:
    if dt is None:
        return None
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = now - dt
    return delta.days


# ---------------------------------------------------------------------------
# Activity normalisation
# ---------------------------------------------------------------------------

# Activity types that are meaningful for "last touch" computation
INBOUND_TYPES = {"Email", "SMS", "Call"}
OUTBOUND_TYPES = {"Email", "EmailThread", "SMS", "Call"}

# Direction fields vary by type:
#   Email / EmailThread: direction = "incoming" | "outgoing" | "both"
#   Call: direction = "inbound" | "outbound"
#   Note: no direction (agent-created)
#   SMS: direction = "incoming" | "outgoing"


def _normalise_activity(act: dict) -> dict:
    """Normalise a raw Close activity into a consistent shape."""
    atype = act.get("_type", "Unknown")
    ts = act.get("activity_at") or act.get("date_created")

    direction = act.get("direction", "")
    # Calls use "inbound"/"outbound", emails use "incoming"/"outgoing"
    if direction in ("inbound", "incoming"):
        dir_norm = "inbound"
    elif direction in ("outbound", "outgoing"):
        dir_norm = "outbound"
    elif atype == "Note":
        dir_norm = "outbound"  # notes are agent-authored
    else:
        dir_norm = direction or "unknown"

    subject = act.get("subject") or act.get("note") or ""
    if isinstance(subject, str) and len(subject) > 120:
        subject = subject[:120] + "…"

    # Body preview
    body = (
        act.get("body_text")
        or act.get("note")
        or act.get("body_preview")
        or act.get("note_html")
        or ""
    )
    if isinstance(body, str) and len(body) > 200:
        body = body[:200] + "…"

    user = act.get("user_name") or act.get("created_by_name") or act.get("user_id") or ""

    return {
        "id": act.get("id"),
        "type": atype,
        "direction": dir_norm,
        "timestamp": ts,
        "subject": subject,
        "preview": body,
        "user": user,
    }


# ---------------------------------------------------------------------------
# Subcommand implementations
# ---------------------------------------------------------------------------

def cmd_find_lead(args) -> None:
    """Resolve a lead + contacts from an email address.

    Uses the Advanced Filtering API (POST /data/search/) to find the contact
    whose email matches, then fetches the full lead.

    Query shape:
      { "query": { "type": "and", "queries": [
          { "type": "object_type", "object_type": "contact" },
          { "type": "has_related",
            "this_object_type": "contact",
            "related_object_type": "contact_email",
            "related_query": {
              "type": "field_condition",
              "field": { "type": "regular_field",
                         "object_type": "contact_email",
                         "field_name": "email" },
              "condition": { "type": "text", "mode": "exact", "value": "<email>" }
            }
          }
        ]},
        "_fields": { "contact": ["id", "lead_id", "name", "emails", "phones", "title"] }
      }
    """
    email = args.email.strip().lower()

    # Advanced Filtering: find contact by email
    payload = {
        "query": {
            "type": "and",
            "queries": [
                {"type": "object_type", "object_type": "contact"},
                # Contact email lives on the related `contact_email` object, not
                # flat on `contact`. Querying contact.email returns
                # HTTP 400 "Field 'email' does not belong to type 'contact'".
                {
                    "type": "has_related",
                    "this_object_type": "contact",
                    "related_object_type": "contact_email",
                    "related_query": {
                        "type": "field_condition",
                        "field": {
                            "type": "regular_field",
                            "object_type": "contact_email",
                            "field_name": "email",
                        },
                        "condition": {
                            "type": "text",
                            "mode": "full_words",
                            "value": email,
                        },
                    },
                },
            ],
        },
        "_fields": {
            "contact": ["id", "lead_id", "name", "display_name", "emails", "phones", "title", "date_created"],
        },
        "_limit": 10,
    }

    search_result = _request("POST", "/data/search/", body=payload)
    contacts = search_result.get("data", [])

    if not contacts:
        _out({"found": False, "email": email, "contacts": [], "leads": []})
        return

    # Collect unique lead IDs
    lead_ids = list({c["lead_id"] for c in contacts if c.get("lead_id")})

    leads = []
    for lid in lead_ids:
        lead = _request("GET", f"/lead/{lid}/")
        leads.append(lead)

    _out({"found": True, "email": email, "contacts": contacts, "leads": leads})


def cmd_find_lead_by_phone(args) -> None:
    """Resolve a lead + contacts from a phone number.

    Mirrors `find-lead` but searches the `contact_phone` related object instead
    of `contact_email`. Used to match VAPI call events (which carry a phone
    number, sometimes no email) back to a Close record.

    Query shape:
      { "query": { "type": "and", "queries": [
          { "type": "object_type", "object_type": "contact" },
          { "type": "has_related",
            "this_object_type": "contact",
            "related_object_type": "contact_phone",
            "related_query": {
              "type": "field_condition",
              "field": { "type": "regular_field",
                         "object_type": "contact_phone",
                         "field_name": "phone" },
              "condition": { "type": "text", "mode": "full_words", "value": "<phone>" }
            }
          }
        ]},
        "_fields": { "contact": ["id", "lead_id", "name", "display_name",
                                 "emails", "phones", "title", "date_created"] }
      }
    """
    raw_phone = args.phone.strip()

    def _search(phone_value: str) -> list:
        payload = {
            "query": {
                "type": "and",
                "queries": [
                    {"type": "object_type", "object_type": "contact"},
                    {
                        "type": "has_related",
                        "this_object_type": "contact",
                        "related_object_type": "contact_phone",
                        "related_query": {
                            "type": "field_condition",
                            "field": {
                                "type": "regular_field",
                                "object_type": "contact_phone",
                                "field_name": "phone",
                            },
                            "condition": {
                                "type": "text",
                                "mode": "full_words",
                                "value": phone_value,
                            },
                        },
                    },
                ],
            },
            "_fields": {
                "contact": [
                    "id", "lead_id", "name", "display_name",
                    "emails", "phones", "title", "date_created",
                ],
            },
            "_limit": 10,
        }
        result = _request("POST", "/data/search/", body=payload)
        return result.get("data", [])

    # Try the raw input first, then a digits-only normalised form (E.164 with a
    # leading "+1" stripped), which tolerates formatting differences in Close.
    contacts = _search(raw_phone)

    digits = "".join(ch for ch in raw_phone if ch.isdigit())
    if not contacts and digits and digits.startswith("1") and len(digits) == 11:
        # "+1XXXXXXXXXX" -> search without the leading country code
        contacts = _search(digits[1:])

    if not contacts:
        _out({"found": False, "phone": raw_phone, "contacts": [], "leads": []})
        return

    lead_ids = list({c["lead_id"] for c in contacts if c.get("lead_id")})

    leads = []
    for lid in lead_ids:
        leads.append(_request("GET", f"/lead/{lid}/"))

    _out({"found": True, "phone": raw_phone, "contacts": contacts, "leads": leads})


def cmd_get_lead(args) -> None:
    """Fetch a single lead by ID."""
    lead = _request("GET", f"/lead/{args.id}/")
    _out(lead)


def cmd_lead_history(args) -> None:
    """Return chronological activity timeline for a lead, newest first.

    Uses GET /activity/?lead_id=X&_order_by=-activity_at
    Normalises each activity to {type, direction, timestamp, subject, preview, user}.
    """
    limit = args.limit if args.limit else 100
    params = {
        "lead_id": args.id,
        "_order_by": "-activity_at",
        "_limit": min(limit, 100),
    }

    activities = []
    skip = 0
    while len(activities) < limit:
        params["_skip"] = skip
        page = _request("GET", "/activity/", params=params)
        data = page.get("data", [])
        activities.extend(data)
        if not page.get("has_more", False) or not data:
            break
        skip += len(data)
        if len(activities) >= limit:
            break

    activities = activities[:limit]
    normalised = [_normalise_activity(a) for a in activities]
    _out({"lead_id": args.id, "count": len(normalised), "activities": normalised})


def cmd_last_touch(args) -> None:
    """Return the most recent inbound and most recent outbound communication.

    Fetches activity for the lead sorted newest-first, then walks the list
    to find the first inbound and first outbound item (Email, Call, SMS only —
    Notes are excluded from inbound, treated as outbound).
    """
    params = {
        "lead_id": args.id,
        "_order_by": "-activity_at",
        "_limit": 100,
    }

    last_inbound = None
    last_outbound = None
    skip = 0

    while last_inbound is None or last_outbound is None:
        params["_skip"] = skip
        page = _request("GET", "/activity/", params=params)
        data = page.get("data", [])
        if not data:
            break

        for act in data:
            norm = _normalise_activity(act)
            atype = norm["type"]
            direction = norm["direction"]
            ts_str = norm["timestamp"]

            # Only consider communication types (not Notes, TaskCompleted, etc.)
            if atype not in {"Email", "EmailThread", "Call", "SMS"}:
                continue

            if direction == "inbound" and last_inbound is None:
                last_inbound = norm
            elif direction == "outbound" and last_outbound is None:
                last_outbound = norm

            if last_inbound is not None and last_outbound is not None:
                break

        if not page.get("has_more", False) or not data:
            break
        skip += len(data)

    def enrich(norm):
        if norm is None:
            return None
        dt = _parse_ts(norm["timestamp"])
        return {**norm, "days_ago": _days_ago(dt)}

    _out({
        "lead_id": args.id,
        "last_inbound": enrich(last_inbound),
        "last_outbound": enrich(last_outbound),
    })


def cmd_create_note(args) -> None:
    """Create a Note activity on a lead.

    POST /activity/note/
    Required: lead_id, note (plaintext) or note_html.
    """
    body = {"lead_id": args.lead_id, "note": args.text}
    result = _request("POST", "/activity/note/", body=body)
    _out(result)


def cmd_update_lead(args) -> None:
    """Update a lead's display name and/or custom fields.

    PUT /lead/{id}/
    Custom fields set via custom.{field_id} keys in the body.
    """
    body: dict = {}

    if args.name:
        body["display_name"] = args.name

    if args.custom_fields:
        try:
            cf = json.loads(args.custom_fields)
        except json.JSONDecodeError as exc:
            _die(f"Invalid JSON in --custom-fields: {exc}")
        for k, v in cf.items():
            body[f"custom.{k}"] = v

    if not body:
        _die("Nothing to update — provide --name and/or --custom-fields")

    result = _request("PUT", f"/lead/{args.lead_id}/", body=body)
    _out(result)


def cmd_create_task(args) -> None:
    """Create a task on a lead, optionally as an outgoing_call task for the voice agent.

    POST /task/
    Two supported types:
      - lead (default): a to-do item. Requires lead_id + text.
      - outgoing_call: a call the voice agent should place. Requires lead_id + contact_id.

    The --type flag selects between them. assigned_to accepts a user id
    (user_...) when you want a specific rep; leave it off to leave unassigned.
    For the voice agent voice: use --type outgoing_call with lead_id + contact_id, and
    note in --text which Voice Agent to use (Booking Re-Engage vs Lead Qualifier).
    """
    _type = args.type or "lead"
    body: dict = {"lead_id": args.lead_id}

    if _type == "lead":
        body["_type"] = "lead"
        if not args.text:
            _die("--text is required for a lead task")
        body["text"] = args.text
        if args.due_date:
            body["due_date"] = args.due_date
        if args.date:
            body["date"] = args.date
    elif _type == "outgoing_call":
        body["_type"] = "outgoing_call"
        if not args.contact_id:
            _die("--contact-id is required for an outgoing_call task")
        body["contact_id"] = args.contact_id
        if args.text:
            body["text"] = args.text
        if args.agent_config_id:
            body["agent_config_id"] = args.agent_config_id
    else:
        _die(f"Unknown task type: {_type} (expected lead or outgoing_call)")

    if args.assigned_to:
        body["assigned_to"] = args.assigned_to
    if args.priority:
        body["priority"] = args.priority

    result = _request("POST", "/task/", body=body)
    _out(result)


def cmd_send_sms(args) -> None:
    """Create an SMS activity. Use status=outbox to send immediately, status=draft to stage.

    POST /activity/sms/
    local_phone must be a Close internal phone number. remote_phone in E.164.
    """
    body = {
        "status": args.status or "draft",
        "text": args.text,
        "local_phone": args.local_phone,
        "remote_phone": args.remote_phone,
        "direction": "outbound",
    }

    if args.lead_id:
        body["lead_id"] = args.lead_id
    if args.contact_id:
        body["contact_id"] = args.contact_id

    if args.status == "scheduled" and args.date_scheduled:
        body["date_scheduled"] = args.date_scheduled

    if args.send_in and args.status == "outbox":
        try:
            body["send_in"] = int(args.send_in)
        except ValueError:
            _die(f"--send-in must be an integer (seconds), got: {args.send_in}")

    result = _request("POST", "/activity/sms/", body=body)
    _out({
        "id": result.get("id"),
        "status": result.get("status"),
        "text": result.get("text"),
        "local_phone": result.get("local_phone"),
        "remote_phone": result.get("remote_phone"),
        "direction": result.get("direction"),
        "lead_id": result.get("lead_id"),
        "contact_id": result.get("contact_id"),
        "date_sent": result.get("date_sent"),
        "error_message": result.get("error_message"),
    })


def cmd_send_email(args) -> None:
    """Create and optionally send an email via Close (POST /activity/email/).

    status semantics (from Close API docs):
      - draft     create a draft to review/send manually (never auto-sent)
      - outbox    actually send immediately; add --send-in (seconds, <60) for an undo window
      - scheduled send at --date-scheduled (ISO 8601)
      - sent      log an already-sent email (sender optional)
      - inbox     log an already-received email

    Required for outbox/scheduled/sent/inbox: lead_id, sender, and either
    body_text/body_html (or a template_id). sender = 'Name <email@domain>'.
    email_account_id routes the send through a specific connected mailbox —
    use it to enforce brand identity (Brand B vs Brand A).
    """
    if not args.lead_id:
        _die("--lead-id is required")
    status = args.status or "draft"
    if status not in {"draft", "outbox", "scheduled", "sent", "inbox", "error"}:
        _die(f"Invalid status: {status}")

    body: dict = {"lead_id": args.lead_id, "status": status}

    if args.contact_id:
        body["contact_id"] = args.contact_id
    if args.sender:
        body["sender"] = args.sender
    if args.to:
        body["to"] = args.to
    if args.cc:
        body["cc"] = args.cc
    if args.bcc:
        body["bcc"] = args.bcc
    if args.subject:
        body["subject"] = args.subject
    if args.body:
        body["body_text"] = args.body
    if args.body_html:
        body["body_html"] = args.body_html
    if args.email_account_id:
        body["email_account_id"] = args.email_account_id
    if args.in_reply_to_id:
        body["in_reply_to_id"] = args.in_reply_to_id
    if args.template_id:
        body["template_id"] = args.template_id
    if args.followup_date:
        body["followup_date"] = args.followup_date

    if status in {"outbox", "scheduled", "sent", "inbox"} and not args.sender:
        _die("--sender is required for outbox/scheduled/sent/inbox (format: 'Name <email>')")
    if status in {"outbox", "scheduled", "sent"} and not (args.body or args.body_html or args.template_id):
        _die("one of --body, --body-html, or --template-id is required to send")
    if status == "scheduled" and not args.date_scheduled:
        _die("--date-scheduled (ISO 8601) is required when status=scheduled")
    if args.date_scheduled:
        body["date_scheduled"] = args.date_scheduled
    if args.send_in and status == "outbox":
        try:
            body["send_in"] = int(args.send_in)
        except ValueError:
            _die(f"--send-in must be an integer (seconds), got: {args.send_in}")

    result = _request("POST", "/activity/email/", body=body)
    _out({
        "id": result.get("id"),
        "status": result.get("status"),
        "email_account_id": result.get("email_account_id"),
        "sender": result.get("sender"),
        "to": result.get("to"),
        "subject": result.get("subject"),
        "direction": result.get("direction"),
        "lead_id": result.get("lead_id"),
        "contact_id": result.get("contact_id"),
        "thread_id": result.get("thread_id"),
        "date_sent": result.get("date_sent"),
        "date_scheduled": result.get("date_scheduled"),
    })


def cmd_list_pipelines(args) -> None:
    """List all pipelines with their opportunity statuses.

    GET /pipeline/   — returns pipelines
    GET /status/opportunity/  — returns all opportunity statuses with pipeline_id
    """
    pipelines = _paginate_offset("/pipeline/")
    statuses = _paginate_offset("/status/opportunity/")

    # Index statuses by pipeline_id
    by_pipeline: dict[str, list] = {}
    for s in statuses:
        pid = s.get("pipeline_id") or "__none__"
        by_pipeline.setdefault(pid, []).append(s)

    result = []
    for p in pipelines:
        pid = p.get("id")
        result.append({
            "id": pid,
            "name": p.get("name"),
            "statuses": by_pipeline.get(pid, []),
        })

    _out({"pipelines": result})


def cmd_set_opportunity_stage(args) -> None:
    """Update an opportunity's pipeline stage (status_id).

    PUT /opportunity/{id}/  — send only the fields to update (patch semantics).
    """
    body = {"status_id": args.status_id}
    result = _request("PUT", f"/opportunity/{args.opportunity_id}/", body=body)
    _out(result)


def cmd_create_opportunity(args) -> None:
    """Create a new opportunity on a lead.

    POST /opportunity/
    Required: lead_id (optional per API, but needed for our use case), status_id
    Optional: value (integer cents), note
    """
    body: dict = {"lead_id": args.lead_id}

    if args.status_id:
        body["status_id"] = args.status_id

    if args.value is not None:
        # Close stores value in the currency's smallest unit (e.g. cents for USD)
        body["value"] = int(args.value)

    if args.note:
        body["note"] = args.note

    result = _request("POST", "/opportunity/", body=body)
    _out(result)


def cmd_list_sequences(args) -> None:
    """List all sequences.

    GET /sequence/
    """
    seqs = _paginate_offset("/sequence/")
    _out({"sequences": seqs, "count": len(seqs)})


def cmd_enroll_sequence(args) -> None:
    """Enroll a contact in a sequence.

    POST /sequence_subscription/
    Required fields (from docs):
      sequence_id, contact_id, sender_account_id (email_account_id)
    Optional but recommended:
      contact_email, sender_email, sender_name
    The API infers lead_id from contact_id, but we pass it explicitly for clarity.
    """
    body: dict = {
        "sequence_id": args.sequence_id,
        "contact_id": args.contact_id,
        "sender_account_id": args.email_account_id,
    }

    # lead_id is returned in the response but the docs show it is inferred;
    # passing it is safe and avoids a lookup on Close's side.
    if args.lead_id:
        body["lead_id"] = args.lead_id

    result = _request("POST", "/sequence_subscription/", body=body)
    _out(result)


def cmd_search(args) -> None:
    """Raw Advanced Filtering escape hatch.

    Accepts a JSON string matching the POST /data/search/ payload shape.
    Example payload:
      {
        "query": { "type": "and", "queries": [
          { "type": "object_type", "object_type": "lead" },
          { "type": "field_condition",
            "field": { "type": "regular_field",
                       "object_type": "lead",
                       "field_name": "status_label" },
            "condition": { "type": "text", "mode": "full_words", "value": "Potential" } }
        ]},
        "_fields": { "lead": ["id", "display_name", "status_label"] },
        "_limit": 50
      }
    """
    try:
        payload = json.loads(args.query)
    except json.JSONDecodeError as exc:
        _die(f"Invalid JSON in --query: {exc}")

    # Paginate using cursor if _limit is set and not already present
    results = []
    cursor = None

    while True:
        if cursor:
            payload["cursor"] = cursor

        page = _request("POST", "/data/search/", body=payload)
        data = page.get("data", [])
        results.extend(data)
        cursor = page.get("cursor")
        if not cursor:
            break

    _out({"count": len(results), "data": results})


# ---------------------------------------------------------------------------
# CLI wiring
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="close_crm",
        description=(
            "Close CRM CLI — reads CLOSE_API_KEY from environment, "
            "outputs JSON to stdout."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # find-lead
    p = sub.add_parser(
        "find-lead",
        help="Resolve a lead and its contacts from an email address.",
    )
    p.add_argument("--email", required=True, help="Email address to search for.")
    p.set_defaults(func=cmd_find_lead)

    # find-lead-by-phone
    p = sub.add_parser(
        "find-lead-by-phone",
        help="Resolve a lead and its contacts from a phone number (for VAPI call events).",
    )
    p.add_argument("--phone", required=True, help="Phone number to search for (any format; E.164 preferred).")
    p.set_defaults(func=cmd_find_lead_by_phone)

    # get-lead
    p = sub.add_parser("get-lead", help="Fetch a lead by ID.")
    p.add_argument("--id", required=True, help="Lead ID (lead_XXX).")
    p.set_defaults(func=cmd_get_lead)

    # lead-history
    p = sub.add_parser(
        "lead-history",
        help="Chronological activity timeline for a lead (newest first).",
    )
    p.add_argument("--id", required=True, help="Lead ID.")
    p.add_argument("--limit", type=int, default=50, help="Max activities to return (default 50).")
    p.set_defaults(func=cmd_lead_history)

    # last-touch
    p = sub.add_parser(
        "last-touch",
        help="Most recent inbound and outbound communication with day deltas.",
    )
    p.add_argument("--id", required=True, help="Lead ID.")
    p.set_defaults(func=cmd_last_touch)

    # create-note
    p = sub.add_parser("create-note", help="Log a note on a lead.")
    p.add_argument("--lead-id", required=True, dest="lead_id", help="Lead ID.")
    p.add_argument("--text", required=True, help="Note text (plaintext).")
    p.set_defaults(func=cmd_create_note)

    # create-task
    p = sub.add_parser(
        "create-task",
        help="Create a task on a lead (type lead or outgoing_call for the voice agent voice). POST /task/.",
    )
    p.add_argument("--lead-id", required=True, dest="lead_id", help="Lead ID (lead_XXX).")
    p.add_argument("--type", default="lead", dest="type", help="lead (default) or outgoing_call.")
    p.add_argument("--text", default=None, help="Task text (required for lead tasks; optional/descriptive for outgoing_call).")
    p.add_argument("--contact-id", default=None, dest="contact_id", help="Contact ID (cont_XXX), required for outgoing_call.")
    p.add_argument("--assigned-to", default=None, dest="assigned_to", help="User ID (user_XXX) to assign to; omit to leave unassigned.")
    p.add_argument("--agent-config-id", default=None, dest="agent_config_id", help="Voice agent config id for outgoing_call tasks.")
    p.add_argument("--due-date", default=None, dest="due_date", help="Due date/datetime (ISO) for lead tasks.")
    p.add_argument("--date", default=None, help="Task date (YYYY-MM-DD or datetime).")
    p.add_argument("--priority", default=None, help="high or medium.")
    p.set_defaults(func=cmd_create_task)

    # send-sms
    p = sub.add_parser(
        "send-sms",
        help="Send or draft an SMS via Close (POST /activity/sms/). Use status=outbox to send, status=draft to stage.",
    )
    p.add_argument("--status", default="draft", help="draft, outbox, scheduled, sent, inbox (default: draft).")
    p.add_argument("--text", required=True, help="SMS body text.")
    p.add_argument("--local-phone", required=True, dest="local_phone", help="Your Close phone number (E.164, e.g. +14155551234).")
    p.add_argument("--remote-phone", required=True, dest="remote_phone", help="Recipient phone number (E.164).")
    p.add_argument("--lead-id", default=None, dest="lead_id", help="Lead ID to associate.")
    p.add_argument("--contact-id", default=None, dest="contact_id", help="Contact ID to associate.")
    p.add_argument("--date-scheduled", default=None, dest="date_scheduled", help="ISO 8601 when status=scheduled.")
    p.add_argument("--send-in", default=None, dest="send_in", help="Delay in seconds for outbox (max 60).")
    p.set_defaults(func=cmd_send_sms)

    # send-email
    p = sub.add_parser(
        "send-email",
        help="Send or draft an email via Close (POST /activity/email/). status=outbox sends now; draft stages for review.",
    )
    p.add_argument("--lead-id", required=True, dest="lead_id", help="Lead ID (lead_XXX).")
    p.add_argument("--status", default="draft", help="draft, outbox, scheduled, sent, inbox (default: draft).")
    p.add_argument("--contact-id", default=None, dest="contact_id", help="Contact ID (cont_XXX).")
    p.add_argument("--sender", default=None, help='Sender as "Name <email@domain>" (required to send).')
    p.add_argument("--to", default=None, nargs="*", help="Recipient email address(es).")
    p.add_argument("--cc", default=None, nargs="*", help="CC email address(es).")
    p.add_argument("--bcc", default=None, nargs="*", help="BCC email address(es).")
    p.add_argument("--subject", default=None, help="Email subject.")
    p.add_argument("--body", default=None, help="Plaintext body.")
    p.add_argument("--body-html", default=None, dest="body_html", help="HTML body.")
    p.add_argument("--email-account-id", default=None, dest="email_account_id", help="Connected mailbox ID (emailacct_XXX) to send from.")
    p.add_argument("--in-reply-to-id", default=None, dest="in_reply_to_id", help="Email activity id to thread this reply under.")
    p.add_argument("--template-id", default=None, dest="template_id", help="Close email template id (server-renders if no body given).")
    p.add_argument("--followup-date", default=None, dest="followup_date", help="Optional ISO datetime to auto-create a followup task if no reply.")
    p.add_argument("--date-scheduled", default=None, dest="date_scheduled", help="ISO 8601 when status=scheduled.")
    p.add_argument("--send-in", default=None, dest="send_in", help="Delay in seconds for outbox (max 60).")
    p.set_defaults(func=cmd_send_email)

    # update-lead
    p = sub.add_parser(
        "update-lead",
        help="Update a lead's name and/or custom fields (PUT /lead/{id}/).",
    )
    p.add_argument("--lead-id", required=True, dest="lead_id", help="Lead ID (lead_XXX).")
    p.add_argument("--name", default=None, help="New display name for the lead (optional).")
    p.add_argument(
        "--custom-fields",
        default=None,
        dest="custom_fields",
        help='JSON object of custom field values, keyed by field ID (e.g. \'{"cf_ABC": "value"}\').',
    )
    p.set_defaults(func=cmd_update_lead)

    # list-pipelines
    p = sub.add_parser("list-pipelines", help="List pipelines with their stages/statuses.")
    p.set_defaults(func=cmd_list_pipelines)

    # set-opportunity-stage
    p = sub.add_parser(
        "set-opportunity-stage",
        help="Move an opportunity to a different pipeline stage.",
    )
    p.add_argument("--opportunity-id", required=True, dest="opportunity_id", help="Opportunity ID (oppo_XXX).")
    p.add_argument("--status-id", required=True, dest="status_id", help="Target status ID (stat_XXX).")
    p.set_defaults(func=cmd_set_opportunity_stage)

    # create-opportunity
    p = sub.add_parser("create-opportunity", help="Create a new opportunity on a lead.")
    p.add_argument("--lead-id", required=True, dest="lead_id", help="Lead ID.")
    p.add_argument("--status-id", dest="status_id", default=None, help="Initial status ID.")
    p.add_argument("--value", type=int, default=None, help="Opportunity value (integer, in currency minor units).")
    p.add_argument("--note", default=None, help="Optional plaintext note.")
    p.set_defaults(func=cmd_create_opportunity)

    # list-sequences
    p = sub.add_parser("list-sequences", help="List available email sequences.")
    p.set_defaults(func=cmd_list_sequences)

    # enroll-sequence
    p = sub.add_parser("enroll-sequence", help="Enroll a contact in an email sequence.")
    p.add_argument("--sequence-id", required=True, dest="sequence_id", help="Sequence ID (seq_XXX).")
    p.add_argument("--contact-id", required=True, dest="contact_id", help="Contact ID (cont_XXX).")
    p.add_argument("--lead-id", required=True, dest="lead_id", help="Lead ID (lead_XXX).")
    p.add_argument(
        "--email-account-id",
        required=True,
        dest="email_account_id",
        help="Connected email account ID (emailacct_XXX) used as sender.",
    )
    p.set_defaults(func=cmd_enroll_sequence)

    # search
    p = sub.add_parser(
        "search",
        help="Raw Advanced Filtering query (POST /data/search/). Pass JSON string.",
    )
    p.add_argument("--query", required=True, help="JSON string with query payload.")
    p.set_defaults(func=cmd_search)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
