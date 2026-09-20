---
name: lead-enrichment
description: "Enrich B2B leads via the Apify actor platform. Crawl a prospect's website for cleaned content, look up a business on Google Maps, and run arbitrary Apify actors synchronously or asynchronously. Produces the company and person context needed to write a credible, specific reply to a cold email response."
when_to_use: "Use before replying to an inbound lead when you need to know who they actually are \u2014 what the company does, how big it is, whether they're a real operator or a tire-kicker. Also for batch-enriching a campaign's respondents. Start with enrich-website; add enrich-company for operators with a thin web presence but a Google Business listing."
tags: ["apify","enrichment","lead-research","scraping","real-estate","brand-a","brand-b"]
auth: api_key
---
# Lead Enrichment via Apify

**Base URL:** `https://api.apify.com/v2/`
**Auth:** `Authorization: Bearer $APIFY_TOKEN`

```
RunWithCredentials(skillName="lead-enrichment", command="python3 skills/apify/apify_client.py <subcommand> [flags]")
```

## Cost discipline — read first

**Every actor run costs real money.** This is not a free API. Before enriching:

- Enrich **one lead at a time, on demand**, when a reply actually warrants a personalized response. Do not batch-enrich a whole campaign list speculatively.
- `enrich-website` on the company domain is the cheapest useful signal and usually enough. Try it before reaching for anything else.
- Check `account-usage` if you're about to run more than a handful.
- Cap crawls with `--max-pages` (default low). A crawl of a large site can run up compute fast.

## Subcommands

### `enrich-website --url X [--max-pages N]`
Crawls a company site via `apify/website-content-crawler`, returns cleaned text. **The default first move** — a prospect's own site tells you what they do, their market, and their scale.

### `enrich-company --name X [--location Y]`
Google Maps lookup via `compass/google-maps-extractor`. Useful for real estate operators who have a GMB listing but a thin or absent website — common in this ICP.

### `run-sync --actor <id> --input '<json>' [--timeout N]`
Runs and returns dataset items inline. **Hard 300-second ceiling** (HTTP 408 past that). Anything slower must go async.

### `run-async --actor <id> --input '<json>'` → `run-status --run-id X` → `dataset-items --dataset-id X`
### `list-actors`
Prints the curated enrichment actor registry with ids and input shapes for runtime discovery.
### `account-usage`
Reports compute units and dollars **spent** this cycle. Note it does not report remaining balance — compare against the plan limit yourself.

## Actor id convention

The `/` in `username/actor-name` becomes `~` in URLs: `apify/website-content-crawler` → `apify~website-content-crawler`. The script converts automatically, so pass either form.

## Curated actors

| Actor ID | Maintainer | Use | Pricing | Confidence |
|---|---|---|---|---|
| `apify/website-content-crawler` | Apify (official) | Site crawl | Compute only | High — 144k users, 4.5★ |
| `compass/google-maps-extractor` | Compass | GMB/local | ~$2.10/1k places | High — 87k users, 4.83★ |
| `dev_fusion/linkedin-profile-scraper` | Community | Person | $10/1k profiles | Medium — 50k users, 4.35★ |
| `powerai/linkedin-company-people-scraper` | Community | Company+people | $4.99/1k | **Low — 321 users, 1★. Avoid.** |

## LinkedIn — a real caveat, not boilerplate

There is **no official Apify LinkedIn scraper**. Every LinkedIn actor here is third-party, and LinkedIn's terms of service prohibit automated scraping. Apify hosts these actors but does not indemnify you.

Practical guidance: prefer `enrich-website` and `enrich-company`, which carry none of this exposure and usually answer the question anyway. If a LinkedIn lookup is genuinely needed for a high-value lead, **surface that to Alex and let him decide** rather than running it silently. Do not build LinkedIn scraping into any automated sweep.

## Run statuses

`READY`, `RUNNING`, `SUCCEEDED`, `FAILED`, `TIMED-OUT`, `ABORTED`.

## Rate limits

60 requests/second per resource. `X-RateLimit-Limit` header carries the per-endpoint limit. The script retries 429s with exponential backoff up to 5 times.

## Lead naming rule (Close lead display name)

When you resolve a lead's identity during enrichment, apply this rule to the Close lead `name` (the `display_name` field — note the write field is `name`, not `display_name`). The goal is always a clean human-readable name, never a `Website Lead: <...>` prefix or other artifact of the intake source.

Priority order:

1. **Company name, when cleanly derivable from the domain.** A URL slug that maps to an obviously-branded real estate operator is enough (e.g. `example-home-offers.com` → "Example Home Offers", `example-cash-offer.com` → "Example Cash Offer", `example-houses.com` → "Example Houses", `exampleco.com` → "ExampleCo LLC"). When the slug is ambiguous or opaque (e.g. `abcx.com`, `qwerty.co`, `xyzco.net`), resolve the real brand — `enrich-website` on the domain homepage title is usually sufficient and nearly free. Do **not** guess a brand from an opaque slug.
2. **Full contact name (first + last),** when the domain doesn't yield a company but the contact has a full name in Close, or the email local-part cleanly reveals a full name (e.g. `janedoe@example.com` → "Jane Doe", `johnsmithnyc@example.com` → "John Smith"). Split CamelCase / numeric-suffixed local-parts into a proper given+surname.
3. **Fallback:** if only a first name is available and nothing in the email or domain resolves a company or surname, leave the lead named as that first name and flag it for manual review — do not fabricate a last name or company.

Apply the same rule uniformly whether the lead arrived from a web form, Facebook ads, or any other source. When you rename a lead as part of enrichment or cleanup, log a note on the lead recording the old → new name so the timeline stays reconstructable.
