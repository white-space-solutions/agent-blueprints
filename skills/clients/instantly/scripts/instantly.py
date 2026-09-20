#!/usr/bin/env python3
"""
Instantly.ai v2 API CLI
Base URL: https://api.instantly.ai
Auth: Authorization: Bearer <INSTANTLY_API_KEY>

Subcommands:
  list-campaigns
  list-replies     --since <ISO8601 | Nd> [--campaign-id X] [--limit N]
  get-lead         --email X
  update-lead      --email X [--status S] [--interest-status S]
  pause-lead       --email X [--campaign-id X]
  add-lead         --campaign-id X --email Y [--first-name F] [--last-name L] [--company C]
"""

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

BASE_URL = "https://api.instantly.ai"

# --------------------------------------------------------------------- helpers

def _get_api_key() -> str:
    key = os.environ.get("INSTANTLY_API_KEY", "").strip()
    if not key:
        _fatal("INSTANTLY_API_KEY environment variable is not set or is empty.")
    return key


def _fatal(msg: str, status: int = 0) -> None:
    """Print an error JSON and exit nonzero."""
    print(json.dumps({"error": msg, "status": status}))
    sys.exit(1)


def _request(
    method: str,
    path: str,
    body=None,        # type: Optional[dict]
    params=None,      # type: Optional[dict]
    _retries: int = 3,
):
    """
    Shared HTTP helper.
    - Injects Bearer auth header.
    - JSON-encodes body; JSON-decodes response.
    - Surfaces HTTP error bodies.
    - Retries on 429 and 5xx with exponential backoff.
    """
    api_key = _get_api_key()
    url = BASE_URL + path
    if params:
        # filter out None values
        clean = {k: str(v) for k, v in params.items() if v is not None}
        url = url + "?" + urllib.parse.urlencode(clean)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        # urllib's default UA ("Python-urllib/3.x") trips Cloudflare's bot-signature
        # filter on api.instantly.ai and returns HTTP 403 error 1010. A normal
        # client UA is required for any request to reach the API at all.
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    }

    data = json.dumps(body).encode("utf-8") if body is not None else None

    for attempt in range(_retries):
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req) as resp:
                raw = resp.read()
                if not raw:
                    return {}
                return json.loads(raw)
        except urllib.error.HTTPError as exc:
            status_code = exc.code
            try:
                err_body = json.loads(exc.read())
            except Exception:
                err_body = {"raw": exc.reason}

            # Retry on 429 or 5xx
            if status_code == 429 or status_code >= 500:
                if attempt < _retries - 1:
                    wait = 2 ** attempt  # 1s, 2s, 4s ...
                    # Honour Retry-After header if present
                    retry_after = exc.headers.get("Retry-After")
                    if retry_after:
                        try:
                            wait = int(retry_after)
                        except ValueError:
                            pass
                    time.sleep(wait)
                    continue
            # Non-retryable or exhausted retries
            msg = err_body.get("message") or err_body.get("error") or str(err_body)
            _fatal(f"HTTP {status_code}: {msg}", status=status_code)
        except urllib.error.URLError as exc:
            if attempt < _retries - 1:
                time.sleep(2 ** attempt)
                continue
            _fatal(f"Network error: {exc.reason}")

    _fatal("Request failed after retries.")


# ----------------------------------------------------------- pagination helper

def _paginate_get(path: str, params: dict, limit=None):  # limit: Optional[int]
    """
    Iterate GET endpoints that use `starting_after` cursor + `next_starting_after`
    response field.  Returns up to `limit` items (None = all).
    """
    items = []
    per_page = 100
    if limit is not None:
        per_page = min(limit, 100)

    current_params = dict(params)
    current_params["limit"] = per_page

    while True:
        resp = _request("GET", path, params=current_params)
        page_items = resp.get("items", []) if isinstance(resp, dict) else []
        items.extend(page_items)

        if limit is not None and len(items) >= limit:
            items = items[:limit]
            break

        next_cursor = resp.get("next_starting_after") if isinstance(resp, dict) else None
        if not next_cursor or not page_items:
            break

        current_params["starting_after"] = next_cursor

    return items


def _paginate_post(path: str, body: dict, limit=None):  # limit: Optional[int]
    """
    Iterate POST list endpoints (e.g. /api/v2/leads/list) with cursor pagination.
    """
    items = []
    per_page = 100
    if limit is not None:
        per_page = min(limit, 100)

    current_body = dict(body)
    current_body["limit"] = per_page

    while True:
        resp = _request("POST", path, body=current_body)
        page_items = resp.get("items", []) if isinstance(resp, dict) else []
        items.extend(page_items)

        if limit is not None and len(items) >= limit:
            items = items[:limit]
            break

        next_cursor = resp.get("next_starting_after") if isinstance(resp, dict) else None
        if not next_cursor or not page_items:
            break

        current_body["starting_after"] = next_cursor

    return items


# ----------------------------------------------------------- date parsing

def _parse_since(since: str) -> str:
    """
    Parse --since value.
    Accepts:
      - Plain ISO8601 string (returned as-is after basic validation)
      - Relative shorthand like '7d', '30d'
    Returns an ISO8601 UTC timestamp string.
    """
    since = since.strip()
    if since.endswith("d") and since[:-1].isdigit():
        days = int(since[:-1])
        dt = datetime.now(timezone.utc) - timedelta(days=days)
        return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    # Assume ISO8601 — pass through
    return since


# ----------------------------------------------------------------- subcommands

def cmd_list_campaigns(args: argparse.Namespace) -> None:
    """GET /api/v2/campaigns"""
    campaigns = _paginate_get("/api/v2/campaigns", params={}, limit=None)
    print(json.dumps(campaigns, indent=2))


def cmd_list_replies(args: argparse.Namespace) -> None:
    """
    GET /api/v2/emails with email_type=received and min_timestamp_created filter.
    Returns inbound replies enriched with: lead email, campaign_id, subject,
    body_text, timestamp_created, thread_id.
    """
    since_ts = _parse_since(args.since) if args.since else None

    params: dict = {
        "email_type": "received",
        "sort_order": "asc",
    }
    if since_ts:
        params["min_timestamp_created"] = since_ts
    if args.campaign_id:
        params["campaign_id"] = args.campaign_id

    limit = int(args.limit) if args.limit else None
    raw_emails = _paginate_get("/api/v2/emails", params=params, limit=limit)

    results = []
    for e in raw_emails:
        results.append({
            "id": e.get("id"),
            "lead_email": e.get("lead"),
            "lead_id": e.get("lead_id"),
            "campaign_id": e.get("campaign_id"),
            "eaccount": e.get("eaccount"),
            "subject": e.get("subject"),
            "body_text": e.get("body"),
            "timestamp_created": e.get("timestamp_created"),
            "thread_id": e.get("thread_id"),
            "is_unread": e.get("is_unread"),
            "is_auto_reply": e.get("is_auto_reply"),
            "ue_type": e.get("ue_type"),  # 2 = received/inbound
        })

    print(json.dumps(results, indent=2))


def _find_lead_by_email(email: str) -> dict:
    """
    Search for a lead by email using POST /api/v2/leads/list with contacts filter.
    Returns the lead dict or calls _fatal if not found.
    """
    resp = _request("POST", "/api/v2/leads/list", body={"contacts": [email], "limit": 1})
    items = resp.get("items", []) if isinstance(resp, dict) else []
    if not items:
        _fatal(f"No lead found with email: {email}", status=404)
    return items[0]


def cmd_get_lead(args: argparse.Namespace) -> None:
    """POST /api/v2/leads/list filtered by email, then GET /api/v2/leads/{id}"""
    lead = _find_lead_by_email(args.email)
    # Fetch full record by id for completeness
    full = _request("GET", f"/api/v2/leads/{lead['id']}")
    print(json.dumps(full, indent=2))


def cmd_update_lead(args: argparse.Namespace) -> None:
    """
    Patch a lead: PATCH /api/v2/leads/{id}
    First resolves email -> lead id via list endpoint.
    Supports --status (lt_interest_status numeric) and/or custom fields.
    """
    lead = _find_lead_by_email(args.email)
    lead_id = lead["id"]

    body: dict = {}
    if args.status is not None:
        body["lt_interest_status"] = int(args.status)
    if args.interest_status is not None:
        body["lt_interest_status"] = int(args.interest_status)

    if not body:
        _fatal("No update fields supplied. Use --status or --interest-status.")

    result = _request("PATCH", f"/api/v2/leads/{lead_id}", body=body)
    print(json.dumps(result, indent=2))


def cmd_pause_lead(args: argparse.Namespace) -> None:
    """
    Stop further sequence emails to a lead.
    Strategy: set lt_interest_status to a value Instantly treats as
    'do not email further'.  The API does not have a dedicated pause endpoint.
    We use lt_interest_status = -1 (Not Interested) as the safe stopping
    signal, which Instantly uses to halt sequence sends.
    If --campaign-id is supplied it is included in the response for tracing
    but the update is global to the lead record.
    """
    lead = _find_lead_by_email(args.email)
    lead_id = lead["id"]

    # -1 = Not Interested stops the sequence.
    # Callers may override by using update-lead with a different status code.
    body = {"lt_interest_status": -1}
    result = _request("PATCH", f"/api/v2/leads/{lead_id}", body=body)
    output = dict(result) if isinstance(result, dict) else {"raw": result}
    if args.campaign_id:
        output["_paused_for_campaign_id"] = args.campaign_id
    print(json.dumps(output, indent=2))


def cmd_get_campaign(args: argparse.Namespace) -> None:
    """GET /api/v2/campaigns/{id} -- full campaign config including sequences."""
    print(json.dumps(_request("GET", f"/api/v2/campaigns/{args.id}"), indent=2))


def cmd_update_campaign(args: argparse.Namespace) -> None:
    """
    PATCH /api/v2/campaigns/{id} -- partial update, including sequence copy.

    Editing a live campaign's sequence changes what every future recipient
    receives, so this is gated the same way sending is:

      * a snapshot is written BEFORE any change, always. That file is the
        rollback. The command refuses to run without --snapshot-dir.
      * nothing is applied without --confirm-apply; without it the command
        prints the payload and exits 0.

    API notes confirmed from the docs 2026-08-14:
      * `sequences` is an array but ONLY the first element is used.
      * each step needs type/delay/variants; each variant needs subject/body.
      * `auto_variant_select` is nullable -- send null to switch it off. There
        is no "off" enum value; the enum is only reply_rate/click_rate/open_rate.
    """
    if not args.snapshot_dir:
        _fatal("--snapshot-dir is required; a rollback copy must exist first", status=2)

    current = _request("GET", f"/api/v2/campaigns/{args.id}")

    os.makedirs(args.snapshot_dir, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    snap = os.path.join(args.snapshot_dir, f"campaign_{args.id}_{stamp}.json")
    with open(snap, "w", encoding="utf-8") as fh:
        json.dump(current, fh, indent=1)

    with open(args.patch_file, "r", encoding="utf-8") as fh:
        patch = json.load(fh)

    if not isinstance(patch, dict) or not patch:
        _fatal("patch file must be a non-empty JSON object", status=2)

    if not args.confirm_apply:
        print(json.dumps({
            "dry_run": True,
            "applied": False,
            "snapshot_written": snap,
            "note": "Nothing changed. Re-run with --confirm-apply to apply.",
            "would_patch_keys": sorted(patch.keys()),
            "would_patch": patch,
        }, indent=2))
        return

    result = _request("PATCH", f"/api/v2/campaigns/{args.id}", body=patch)
    print(json.dumps({
        "applied": True,
        "snapshot_written": snap,
        "campaign_id": args.id,
        "name": (result or {}).get("name"),
        "auto_variant_select": (result or {}).get("auto_variant_select", "absent"),
        "sequences": (result or {}).get("sequences"),
    }, indent=2))


def cmd_reply_to_email(args: argparse.Namespace) -> None:
    """
    POST /api/v2/emails/reply  -- send an in-thread reply to an inbound email.

    This is the ONLY send path in this skill, and it is deliberately gated.

    `--reply-to-uuid` is the `id` field of the email being replied to, exactly as
    returned by `list-replies`. Instantly threads the reply off that id, so the
    prospect sees it as a normal continuation of the conversation.

    SAFETY: nothing is sent unless `--confirm-send` is passed. Without it this
    prints the exact payload it would POST and exits 0. Keep it that way. A
    prospect-facing send is not a retryable operation, and the default posture
    for this skill is draft-then-human-approve.
    """
    if args.body_file:
        with open(args.body_file, "r", encoding="utf-8") as fh:
            text = fh.read()
    elif args.body_text:
        text = args.body_text
    else:
        _fatal("Provide the reply body via --body-text or --body-file", status=2)

    text = text.rstrip("\n")

    body: dict = {
        "eaccount": args.eaccount,
        "reply_to_uuid": args.reply_to_uuid,
        "subject": args.subject,
        # Instantly renders `html` for the delivered message and needs explicit
        # <br/> tags; plain newlines collapse. Send both so the text part stays
        # readable in clients that prefer it.
        "body": {
            "text": text,
            "html": text.replace("&", "&amp;").replace("<", "&lt;")
                        .replace(">", "&gt;").replace("\n", "<br/>"),
        },
    }
    if args.cc:
        body["cc_address_email_list"] = args.cc
    if args.bcc:
        body["bcc_address_email_list"] = args.bcc

    if not args.confirm_send:
        print(json.dumps({
            "dry_run": True,
            "sent": False,
            "note": "Nothing sent. Re-run with --confirm-send to actually send.",
            "would_post": {"endpoint": "/api/v2/emails/reply", "body": body},
        }, indent=2))
        return

    result = _request("POST", "/api/v2/emails/reply", body=body)
    output = dict(result) if isinstance(result, dict) else {"raw": result}
    output["_sent"] = True
    print(json.dumps(output, indent=2))


def cmd_add_lead(args: argparse.Namespace) -> None:
    """POST /api/v2/leads"""
    body: dict = {
        "campaign": args.campaign_id,
        "email": args.email,
    }
    if args.first_name:
        body["first_name"] = args.first_name
    if args.last_name:
        body["last_name"] = args.last_name
    if args.company:
        body["company_name"] = args.company

    result = _request("POST", "/api/v2/leads", body=body)
    print(json.dumps(result, indent=2))


# ----------------------------------------------------------------------- main

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="instantly",
        description=(
            "Instantly.ai v2 API CLI. Set INSTANTLY_API_KEY env var before use.\n\n"
            "Interest status codes:\n"
            "  1=Interested  2=Meeting Booked  3=Meeting Completed  4=Won\n"
            "  0=Out of Office  -1=Not Interested  -2=Wrong Person\n"
            "  -3=Lost  -4=No Show"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    # list-campaigns
    sub.add_parser(
        "list-campaigns",
        help="List all campaigns (id, name, status)",
    )

    # list-replies
    p_lr = sub.add_parser(
        "list-replies",
        help="List inbound reply emails, optionally filtered by date/campaign",
    )
    p_lr.add_argument(
        "--since",
        metavar="DATE",
        help="Return replies created after this date. ISO8601 (e.g. 2024-01-01T00:00:00Z) or relative (e.g. 7d)",
    )
    p_lr.add_argument("--campaign-id", metavar="ID", help="Filter by campaign UUID")
    p_lr.add_argument("--limit", metavar="N", type=int, help="Max replies to return")

    # get-lead
    p_gl = sub.add_parser("get-lead", help="Get full lead record by email address")
    p_gl.add_argument("--email", required=True, metavar="EMAIL", help="Lead email address")

    # update-lead
    p_ul = sub.add_parser("update-lead", help="Update lead interest status")
    p_ul.add_argument("--email", required=True, metavar="EMAIL", help="Lead email address")
    p_ul.add_argument(
        "--status",
        metavar="N",
        help="Set lt_interest_status (numeric). Same as --interest-status.",
    )
    p_ul.add_argument(
        "--interest-status",
        metavar="N",
        help=(
            "Set lt_interest_status numeric value. "
            "1=Interested, 2=Meeting Booked, 3=Meeting Completed, 4=Won, "
            "0=Out of Office, -1=Not Interested, -2=Wrong Person, -3=Lost, -4=No Show"
        ),
    )

    # pause-lead
    p_pl = sub.add_parser(
        "pause-lead",
        help="Stop further sequence emails to a lead (sets interest status to Not Interested=-1)",
    )
    p_pl.add_argument("--email", required=True, metavar="EMAIL", help="Lead email address")
    p_pl.add_argument("--campaign-id", metavar="ID", help="Campaign context (for logging only)")

    # add-lead
    p_al = sub.add_parser("add-lead", help="Add/enroll a lead in a campaign")
    p_al.add_argument("--campaign-id", required=True, metavar="ID", help="Campaign UUID")
    p_al.add_argument("--email", required=True, metavar="EMAIL", help="Lead email address")
    p_al.add_argument("--first-name", metavar="NAME", help="Lead first name")
    p_al.add_argument("--last-name", metavar="NAME", help="Lead last name")
    p_al.add_argument("--company", metavar="NAME", help="Lead company name")

    # reply-to-email
    p_re = sub.add_parser(
        "reply-to-email",
        help="Send an in-thread reply to an inbound email (requires --confirm-send)",
    )
    p_re.add_argument("--eaccount", required=True, metavar="EMAIL",
                      help="Connected sending mailbox, must match the thread")
    p_re.add_argument("--reply-to-uuid", required=True, metavar="ID",
                      help="The `id` of the inbound email, from list-replies")
    p_re.add_argument("--subject", required=True, metavar="TEXT", help="Reply subject line")
    p_re.add_argument("--body-text", metavar="TEXT", help="Reply body as a literal string")
    p_re.add_argument("--body-file", metavar="PATH",
                      help="Read reply body from a file (preferred for multi-line copy)")
    p_re.add_argument("--cc", metavar="EMAILS", help="Comma-separated CC list")
    p_re.add_argument("--bcc", metavar="EMAILS", help="Comma-separated BCC list")
    p_re.add_argument("--confirm-send", action="store_true",
                      help="Actually send. Without this flag the command is a dry run.")

    # get-campaign
    p_gc = sub.add_parser("get-campaign", help="Get full campaign config including sequences")
    p_gc.add_argument("--id", required=True, metavar="ID", help="Campaign UUID")

    # update-campaign
    p_uc = sub.add_parser(
        "update-campaign",
        help="PATCH a campaign (incl. sequence copy). Snapshot required; dry run unless --confirm-apply",
    )
    p_uc.add_argument("--id", required=True, metavar="ID", help="Campaign UUID")
    p_uc.add_argument("--patch-file", required=True, metavar="PATH",
                      help="JSON file containing the partial update body")
    p_uc.add_argument("--snapshot-dir", required=True, metavar="DIR",
                      help="Directory to write the pre-change rollback snapshot")
    p_uc.add_argument("--confirm-apply", action="store_true",
                      help="Actually apply. Without this flag the command is a dry run.")

    return parser


COMMAND_MAP = {
    "list-campaigns": cmd_list_campaigns,
    "list-replies": cmd_list_replies,
    "get-lead": cmd_get_lead,
    "update-lead": cmd_update_lead,
    "pause-lead": cmd_pause_lead,
    "add-lead": cmd_add_lead,
    "reply-to-email": cmd_reply_to_email,
    "get-campaign": cmd_get_campaign,
    "update-campaign": cmd_update_campaign,
}


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    fn = COMMAND_MAP.get(args.command)
    if fn is None:
        _fatal(f"Unknown command: {args.command}")
    fn(args)


if __name__ == "__main__":
    main()
