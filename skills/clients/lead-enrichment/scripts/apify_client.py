#!/usr/bin/env python3
"""
apify_client.py — CLI for running Apify actors in a lead-enrichment pipeline.

Usage:
    python apify_client.py <subcommand> [options]

Reads APIFY_TOKEN from environment.  All output is JSON to stdout.
On error, prints {"error": "...", "status": N} and exits nonzero.

Verified API base: https://api.apify.com/v2/
Auth:              Authorization: Bearer <APIFY_TOKEN>
Sync endpoint:     POST /v2/actors/{actorId}/run-sync-get-dataset-items
                   - actorId uses ~ instead of / (e.g. apify~website-content-crawler)
                   - ?timeout=N (seconds, hard ceiling 300 s on Apify side)
                   - body is the actor INPUT JSON (Content-Type: application/json)
Async run:         POST /v2/actors/{actorId}/runs
Poll run:          GET  /v2/actor-runs/{runId}
Fetch dataset:     GET  /v2/datasets/{datasetId}/items?limit=N&offset=N
Account usage:     GET  /v2/users/me/usage/monthly
Rate limit:        60 req/s per resource (default); exponential backoff on 429/5xx
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Union

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URL = "https://api.apify.com/v2"
SYNC_TIMEOUT_CEILING = 295          # Apify hard-kills at 300 s; stay just under
DEFAULT_SOCKET_TIMEOUT = 320        # socket-level timeout (seconds)
DEFAULT_POLL_INTERVAL = 5           # async polling interval (seconds)
MAX_RETRIES = 5

# ---------------------------------------------------------------------------
# Curated enrichment actors
# ---------------------------------------------------------------------------
# Sourced from apify.com store pages (all verified against live store pages
# as of 2026-08).  See AMBIGUITIES section at bottom of this file.

ENRICHMENT_ACTORS = [
    {
        "id": "apify/website-content-crawler",
        "store_url": "https://apify.com/apify/website-content-crawler",
        "description": "Deep-crawl any website; returns clean Markdown/text per page. "
                       "Ideal for reading company websites before outreach.",
        "maintained_by": "Apify (official)",
        "pricing": "Pay-per-usage (platform compute only; no per-result surcharge)",
        "input_schema": {
            "startUrls": [{"url": "https://example.com"}],   # required
            "maxCrawlingDepth": 1,          # 0 = just the start URL
            "maxPagesPerCrawl": 5,          # keep small for enrichment
            "crawlerType": "cheerio",       # 'cheerio' (fast/light) | 'playwright:firefox'
            "outputFormats": ["markdown"],  # 'markdown' | 'text' | 'html'
        },
        "output_fields": ["url", "title", "text", "markdown"],
        "notes": "Official Apify actor. 144 k+ users, 4.5-star rating.",
    },
    {
        "id": "compass/google-maps-extractor",
        "store_url": "https://apify.com/compass/google-maps-extractor",
        "description": "Search Google Maps by keyword + location; returns business name, "
                       "address, phone, website, rating, hours, GPS. "
                       "Great for small business operators with thin web presence but a GMB listing.",
        "maintained_by": "Compass (Apify team member — effectively Apify-maintained)",
        "pricing": "Pay-per-event: from ~$2.10 / 1,000 places scraped",
        "input_schema": {
            "searchStringsArray": ["your niche keyword"],   # required
            "locationQuery": "Houston, TX",                     # city / address / polygon
            "maxCrawledPlacesPerSearch": 10,
            "scrapePlaceDetailPage": False,  # True adds $0.002/place for hours, reviews, etc.
            "scrapeContacts": False,
        },
        "output_fields": [
            "title", "address", "phone", "website", "rating", "reviewCount",
            "categoryName", "location", "url",
        ],
        "notes": "87 k+ users, 4.83 stars. Companion 'crawler-google-places' is cheaper "
                 "but slower; extractor is faster with predictable pricing.",
    },
    {
        "id": "dev_fusion/linkedin-profile-scraper",
        "store_url": "https://apify.com/dev_fusion/linkedin-profile-scraper",
        "description": "Enrich LinkedIn person profiles: full name, headline, work history, "
                       "education, skills, email discovery, company details. No cookies needed.",
        "maintained_by": "Dev Fusion (community — third-party)",
        "pricing": "$10.00 / 1,000 results (pay-per-event)",
        "input_schema": {
            "profileUrls": ["https://www.linkedin.com/in/example-person"],  # required array
        },
        "output_fields": [
            "fullName", "headline", "email", "mobileNumber",
            "workExperience", "education", "skills", "companyName",
            "companyIndustry", "companySize",
        ],
        "notes": "Community actor. 50 k+ users, 4.35 stars. Free tier: max 10 profiles/run, "
                 "10 runs/day, UI-only. Paying users: API access, mobile lookup, unlimited.",
    },
    {
        "id": "powerai/linkedin-company-people-scraper",
        "store_url": "https://apify.com/powerai/linkedin-company-people-scraper",
        "description": "Scrape LinkedIn company profiles OR person profiles by keyword, "
                       "name, or URL. Returns company description, headcount, followers, "
                       "website, HQ; or person work history, education, certifications.",
        "maintained_by": "PowerAI (community — third-party)",
        "pricing": "From $4.99 / 1,000 results (pay-per-event)",
        "input_schema": {
            "operationType": "companies",  # 'companies' | 'profiles'
            "searchTerms": ["Acme Co"],
            "queryByUrl": False,
            "queryByName": False,
            "maxResults": 3,
            "locations": [],
        },
        "output_fields": [
            "companyName", "companyUrl", "companyDescription", "industries",
            "website", "headquarters", "totalEmployees", "totalFollowers",
        ],
        "notes": "Community actor. 321 total users, 43 monthly. 1-star user rating — "
                 "RELIABILITY UNVERIFIED. Use with caution; prefer official alternatives. "
                 "Apify does NOT officially maintain this actor.",
    },
]

# ---------------------------------------------------------------------------
# Shared HTTP helper
# ---------------------------------------------------------------------------

def _get_token() -> str:
    token = os.environ.get("APIFY_TOKEN", "").strip()
    if not token:
        _die("APIFY_TOKEN environment variable is not set or is empty", 401)
    return token


def _die(message: str, status: int = 1) -> None:
    print(json.dumps({"error": message, "status": status}), file=sys.stderr)
    sys.exit(1)


def _request(
    path: str,
    method: str = "GET",
    body: Optional[Dict] = None,
    params: Optional[Dict] = None,
    socket_timeout: int = DEFAULT_SOCKET_TIMEOUT,
) -> Union[Dict, List]:
    """
    Shared HTTP helper.  Retries on 429 and 5xx with exponential backoff.
    Returns parsed JSON response body.

    path    — path relative to BASE_URL, e.g. '/actors/apify~foo/runs'
    method  — HTTP verb
    body    — dict serialised as JSON request body
    params  — dict of URL query parameters
    """
    token = _get_token()
    url = BASE_URL + path
    if params:
        query = "&".join(
            f"{k}={urllib.request.quote(str(v))}" for k, v in params.items() if v is not None
        )
        url = f"{url}?{query}"

    encoded_body = json.dumps(body).encode("utf-8") if body is not None else None

    delay = 2
    last_err: Optional[Exception] = None
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(
                url,
                data=encoded_body,
                method=method,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": "apify-lead-enrichment-cli/1.0",
                },
            )
            with urllib.request.urlopen(req, timeout=socket_timeout) as resp:
                raw = resp.read()
                if not raw:
                    return {}
                return json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            status_code = exc.code
            body_text = ""
            try:
                body_text = exc.read().decode("utf-8", errors="replace")
            except Exception:
                pass

            if status_code == 408:
                # Sync endpoint timed out — caller should use run-async
                _die(
                    f"Actor run timed out (HTTP 408). The sync ceiling is {SYNC_TIMEOUT_CEILING}s. "
                    "Use the 'run-async' subcommand for long-running actors.",
                    408,
                )

            if status_code == 429 or status_code >= 500:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(delay)
                    delay = min(delay * 2, 60)
                    last_err = exc
                    continue

            # Non-retryable HTTP error
            try:
                err_body = json.loads(body_text)
                msg = err_body.get("error", {}).get("message", body_text)
            except Exception:
                msg = body_text or str(exc)
            _die(f"HTTP {status_code}: {msg}", status_code)

        except TimeoutError as exc:
            _die(
                f"Socket timeout after {socket_timeout}s waiting for Apify. "
                "For long actors use 'run-async' subcommand.",
                408,
            )
        except Exception as exc:
            if attempt < MAX_RETRIES - 1:
                time.sleep(delay)
                delay = min(delay * 2, 60)
                last_err = exc
                continue
            _die(f"Request failed: {exc}", 500)

    _die(f"Exhausted {MAX_RETRIES} retries. Last error: {last_err}", 500)


# ---------------------------------------------------------------------------
# Subcommand implementations
# ---------------------------------------------------------------------------

def cmd_run_sync(args: argparse.Namespace) -> None:
    """POST /actors/{actorId}/run-sync-get-dataset-items"""
    try:
        actor_input = json.loads(args.input)
    except json.JSONDecodeError as exc:
        _die(f"--input is not valid JSON: {exc}", 400)

    actor_id = args.actor.replace("/", "~")
    params: dict = {}
    if args.timeout:
        if args.timeout > SYNC_TIMEOUT_CEILING:
            _die(
                f"Sync timeout ceiling is {SYNC_TIMEOUT_CEILING}s. "
                f"Requested {args.timeout}s — use 'run-async' instead.",
                400,
            )
        params["timeout"] = args.timeout

    # Add generous socket timeout: actor timeout + 30 s for network overhead
    sock_timeout = (args.timeout or SYNC_TIMEOUT_CEILING) + 30

    result = _request(
        f"/actors/{actor_id}/run-sync-get-dataset-items",
        method="POST",
        body=actor_input,
        params=params or None,
        socket_timeout=sock_timeout,
    )
    print(json.dumps(result, indent=2))


def cmd_run_async(args: argparse.Namespace) -> None:
    """POST /actors/{actorId}/runs — fire and return immediately."""
    try:
        actor_input = json.loads(args.input)
    except json.JSONDecodeError as exc:
        _die(f"--input is not valid JSON: {exc}", 400)

    actor_id = args.actor.replace("/", "~")
    result = _request(
        f"/actors/{actor_id}/runs",
        method="POST",
        body=actor_input,
    )
    run = result.get("data", result)
    print(json.dumps({
        "runId": run.get("id"),
        "status": run.get("status"),
        "defaultDatasetId": run.get("defaultDatasetId"),
        "startedAt": run.get("startedAt"),
        "raw": run,
    }, indent=2))


def cmd_run_status(args: argparse.Namespace) -> None:
    """GET /actor-runs/{runId}"""
    result = _request(f"/actor-runs/{args.run_id}")
    run = result.get("data", result)
    print(json.dumps({
        "runId": run.get("id"),
        "status": run.get("status"),      # READY|RUNNING|SUCCEEDED|FAILED|TIMED-OUT|ABORTED
        "defaultDatasetId": run.get("defaultDatasetId"),
        "startedAt": run.get("startedAt"),
        "finishedAt": run.get("finishedAt"),
        "exitCode": run.get("exitCode"),
        "raw": run,
    }, indent=2))


def cmd_dataset_items(args: argparse.Namespace) -> None:
    """GET /datasets/{datasetId}/items"""
    params: dict = {}
    if args.limit is not None:
        params["limit"] = args.limit
    if args.offset is not None:
        params["offset"] = args.offset
    result = _request(f"/datasets/{args.dataset_id}/items", params=params or None)
    # Dataset items endpoint returns a list directly (or wrapped in data.items)
    if isinstance(result, list):
        print(json.dumps(result, indent=2))
    else:
        print(json.dumps(result.get("data", {}).get("items", result), indent=2))


def cmd_enrich_website(args: argparse.Namespace) -> None:
    """
    Convenience wrapper: run apify/website-content-crawler against one URL.
    Returns a list of {url, title, text} objects (one per crawled page).
    """
    max_pages = args.max_pages if args.max_pages else 5
    actor_input = {
        "startUrls": [{"url": args.url}],
        "maxCrawlingDepth": 1,
        "maxPagesPerCrawl": max_pages,
        "crawlerType": "cheerio",
        "outputFormats": ["markdown"],
    }
    actor_id = "apify~website-content-crawler"
    params = {"timeout": SYNC_TIMEOUT_CEILING}
    result = _request(
        f"/actors/{actor_id}/run-sync-get-dataset-items",
        method="POST",
        body=actor_input,
        params=params,
        socket_timeout=SYNC_TIMEOUT_CEILING + 30,
    )
    # Extract clean text
    pages = result if isinstance(result, list) else []
    cleaned = []
    for page in pages:
        cleaned.append({
            "url": page.get("url"),
            "title": page.get("metadata", {}).get("title") or page.get("title"),
            "text": (page.get("markdown") or page.get("text") or "")[:4000],  # trim for LLM
        })
    print(json.dumps(cleaned, indent=2))


def cmd_enrich_company(args: argparse.Namespace) -> None:
    """
    Convenience wrapper: search Google Maps for a company by name + optional location.
    Uses compass/google-maps-extractor (Apify-team maintained, pay-per-event).
    Returns matching business records.
    """
    search_query = args.name
    if args.location:
        search_query = f"{args.name} {args.location}"

    actor_input = {
        "searchStringsArray": [search_query],
        "maxCrawledPlacesPerSearch": 5,
        "scrapePlaceDetailPage": False,
        "scrapeContacts": False,
    }
    if args.location:
        actor_input["locationQuery"] = args.location

    actor_id = "compass~google-maps-extractor"
    params = {"timeout": SYNC_TIMEOUT_CEILING}
    result = _request(
        f"/actors/{actor_id}/run-sync-get-dataset-items",
        method="POST",
        body=actor_input,
        params=params,
        socket_timeout=SYNC_TIMEOUT_CEILING + 30,
    )
    items = result if isinstance(result, list) else []
    print(json.dumps(items, indent=2))


def cmd_list_actors(_args: argparse.Namespace) -> None:
    """Print the curated enrichment actor registry as JSON."""
    print(json.dumps(ENRICHMENT_ACTORS, indent=2))


def cmd_account_usage(_args: argparse.Namespace) -> None:
    """GET /users/me/usage/monthly"""
    result = _request("/users/me/usage/monthly")
    print(json.dumps(result, indent=2))


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="apify_client.py",
        description=(
            "CLI client for the Apify API (https://api.apify.com/v2/).\n"
            "Reads APIFY_TOKEN from environment. All output is JSON.\n\n"
            "Actor ID format: use username~actor-name (tilde) in URLs;\n"
            "this script also accepts username/actor-name and converts automatically.\n\n"
            "Run statuses: READY | RUNNING | SUCCEEDED | FAILED | TIMED-OUT | ABORTED"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", metavar="<subcommand>")
    sub.required = True

    # run-sync
    p = sub.add_parser(
        "run-sync",
        help="Run actor synchronously and return dataset items inline (max ~295 s).",
        description=(
            "POST /v2/actors/{actorId}/run-sync-get-dataset-items\n"
            "Actor input JSON is passed as the request body.\n"
            "Returns dataset items directly. If the actor takes > 295 s, use run-async."
        ),
    )
    p.add_argument("--actor", required=True,
                   help="Actor ID, e.g. 'apify/website-content-crawler' or 'apify~website-content-crawler'")
    p.add_argument("--input", required=True,
                   help="Actor input as a JSON string, e.g. '{\"startUrls\":[{\"url\":\"https://example.com\"}]}'")
    p.add_argument("--timeout", type=int, default=None,
                   help=f"Run timeout in seconds (max {SYNC_TIMEOUT_CEILING}). Default: actor's own config.")
    p.set_defaults(func=cmd_run_sync)

    # run-async
    p = sub.add_parser(
        "run-async",
        help="Start actor run asynchronously; returns runId + datasetId immediately.",
        description=(
            "POST /v2/actors/{actorId}/runs\n"
            "Fires the actor and returns immediately with runId and defaultDatasetId.\n"
            "Use run-status to poll and dataset-items to fetch results."
        ),
    )
    p.add_argument("--actor", required=True,
                   help="Actor ID, e.g. 'apify/website-content-crawler'")
    p.add_argument("--input", required=True,
                   help="Actor input as a JSON string")
    p.set_defaults(func=cmd_run_async)

    # run-status
    p = sub.add_parser(
        "run-status",
        help="Poll the status of an actor run.",
        description="GET /v2/actor-runs/{runId}\nReturns status, datasetId, timing.",
    )
    p.add_argument("--run-id", required=True, help="Run ID returned by run-async")
    p.set_defaults(func=cmd_run_status)

    # dataset-items
    p = sub.add_parser(
        "dataset-items",
        help="Fetch items from a dataset.",
        description=(
            "GET /v2/datasets/{datasetId}/items\n"
            "Paginate with --limit and --offset."
        ),
    )
    p.add_argument("--dataset-id", required=True,
                   help="Dataset ID (from run response defaultDatasetId)")
    p.add_argument("--limit", type=int, default=None,
                   help="Max items to return")
    p.add_argument("--offset", type=int, default=None,
                   help="Number of items to skip")
    p.set_defaults(func=cmd_dataset_items)

    # enrich-website
    p = sub.add_parser(
        "enrich-website",
        help="Crawl a company website and return cleaned page text (uses apify/website-content-crawler).",
        description=(
            "Convenience wrapper: crawls the given URL up to --max-pages pages\n"
            "and returns [{url, title, text}] suitable for feeding to an LLM.\n"
            "Actor: apify/website-content-crawler (official, pay-per-usage)."
        ),
    )
    p.add_argument("--url", required=True, help="Company website URL to crawl")
    p.add_argument("--max-pages", type=int, default=5,
                   help="Max pages to crawl (default: 5)")
    p.set_defaults(func=cmd_enrich_website)

    # enrich-company
    p = sub.add_parser(
        "enrich-company",
        help="Look up a company on Google Maps (uses compass/google-maps-extractor).",
        description=(
            "Convenience wrapper: searches Google Maps for the company name,\n"
            "optionally filtered by location. Returns business name, address,\n"
            "phone, website, rating, GPS coords.\n"
            "Actor: compass/google-maps-extractor (Apify-team maintained, pay-per-event ~$2.10/1k)."
        ),
    )
    p.add_argument("--name", required=True,
                   help="Company / business name to search")
    p.add_argument("--location", default=None,
                   help="City or area to restrict search, e.g. 'Houston, TX'")
    p.set_defaults(func=cmd_enrich_company)

    # list-actors
    p = sub.add_parser(
        "list-actors",
        help="Print the curated enrichment actor registry as JSON.",
        description=(
            "Returns the built-in list of vetted actors with their IDs, input schemas,\n"
            "pricing, and reliability notes. Useful for runtime actor discovery."
        ),
    )
    p.set_defaults(func=cmd_list_actors)

    # account-usage
    p = sub.add_parser(
        "account-usage",
        help="Show current monthly usage and credit spend.",
        description=(
            "GET /v2/users/me/usage/monthly\n"
            "Returns compute units, data transfer, storage, and dollar totals\n"
            "for the current billing cycle."
        ),
    )
    p.set_defaults(func=cmd_account_usage)

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()


# ---------------------------------------------------------------------------
# AMBIGUITIES AND UNVERIFIED ITEMS
# ---------------------------------------------------------------------------
#
# 1. LinkedIn company scraper (officially Apify-maintained):
#    Apify does NOT publish an official first-party LinkedIn company scraper
#    the way it does for website-content-crawler.  The two actors included
#    (powerai/linkedin-company-people-scraper and dev_fusion/linkedin-profile-scraper)
#    are third-party community actors.  powerai's actor has only 321 total users and
#    a 1-star rating — it is flagged as RELIABILITY UNVERIFIED.  dev_fusion's actor
#    has 50 k+ users and 4.35 stars and is the safer choice for person enrichment.
#
# 2. LinkedIn scraping legality:
#    LinkedIn's ToS prohibits automated scraping.  Apify hosts these actors but does
#    not endorse the legality.  Use at your own legal risk; consult counsel if
#    deploying at scale or for commercial lead generation.
#
# 3. Sync timeout ceiling:
#    Documented at 300 s (HTTP 408 returned if exceeded).  This is a hard Apify
#    platform limit; the timeout query param cannot extend it beyond 300 s.
#
# 4. Rate limits:
#    Default: 60 requests/second per resource (confirmed from docs).
#    The _request() helper retries with exponential backoff on 429 and 5xx.
#
# 5. Google Maps Extractor (compass/google-maps-extractor):
#    Developed by "Compass", who is an Apify team member, making this
#    effectively Apify-maintained.  Confirmed 87 k+ users, 4.83 stars.
#    Pricing is pay-per-event starting at ~$2.10/1,000 places.
#
# 6. account-usage endpoint returns ACTOR_COMPUTE_UNITS and dollar totals.
#    It does NOT return a simple "remaining credits" balance; you need to
#    compare against your plan limit manually.
#
# 7. Auth: Both Authorization: Bearer header (recommended) and ?token= query
#    param are supported.  This client uses the header exclusively.
