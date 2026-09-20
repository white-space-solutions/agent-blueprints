#!/usr/bin/env python3
"""
Manage Instantly.ai v2 webhook subscriptions.

Subcommands:
  list                      GET /api/v2/webhooks
  event-types               GET /api/v2/webhooks/event-types
  create    --url URL [--event TYPE] [--name NAME] [--secret S] [--header NAME]
  patch     --id ID [--url URL] [--secret S] [--header NAME]
  test      --id ID         POST /api/v2/webhooks/{id}/test
  delete    --id ID         DELETE /api/v2/webhooks/{id}

Canonical target for the Lead Management Agent (correct as of 2026-08-21):
  URL:    https://hyperagent.com/api/webhooks/<webhook-endpoint-id>/receive
  Secret header name:  X-Hyperagent-Webhook-Secret
  Secret value:        <HYPERAGENT_WEBHOOK_SECRET>

Auth note: Hyperagent webhook endpoints authenticate via the
  `X-Hyperagent-Webhook-Secret` header, NOT the standard `Authorization: Bearer`.
  Instantly's /test endpoint does NOT attach custom delivery headers, so it will
  always return 401 against a Hyperagent endpoint — test delivery by POSTing
  directly to the URL with curl instead.
"""
import argparse, json, os, sys, urllib.request, urllib.error

BASE = "https://api.instantly.ai"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


def key():
    k = os.environ.get("INSTANTLY_API_KEY", "").strip()
    if not k:
        print(json.dumps({"error": "INSTANTLY_API_KEY not set"})); sys.exit(1)
    return k


def req(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method, headers={
        "Authorization": "Bearer " + key(), "Content-Type": "application/json",
        "Accept": "application/json", "User-Agent": UA})
    try:
        with urllib.request.urlopen(r) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def main():
    p = argparse.ArgumentParser()
    s = p.add_subparsers(dest="cmd", required=True)

    s.add_parser("list")
    s.add_parser("event-types")

    c = s.add_parser("create")
    c.add_argument("--url", required=True)
    c.add_argument("--event", default="reply_received")
    c.add_argument("--name")
    c.add_argument("--secret")
    c.add_argument("--header", default="X-Hyperagent-Webhook-Secret")

    t = s.add_parser("test")
    t.add_argument("--id", required=True)

    d = s.add_parser("delete")
    d.add_argument("--id", required=True)

    pth = s.add_parser("patch")
    pth.add_argument("--id", required=True)
    pth.add_argument("--url")
    pth.add_argument("--secret")
    pth.add_argument("--header", default="X-Hyperagent-Webhook-Secret")

    a = p.parse_args()

    if a.cmd == "list":
        code, r = req("GET", "/api/v2/webhooks"); print(json.dumps({"status": code, "webhooks": r}, indent=2, default=str))
    elif a.cmd == "event-types":
        code, r = req("GET", "/api/v2/webhooks/event-types"); print(json.dumps({"status": code, "event_types": r}, indent=2, default=str))
    elif a.cmd == "create":
        body = {"target_hook_url": a.url, "event_type": a.event}
        if a.name: body["name"] = a.name
        if a.secret: body["headers"] = {a.header: a.secret}
        code, r = req("POST", "/api/v2/webhooks", body); print(json.dumps({"status": code, "webhook": r}, indent=2, default=str))
    elif a.cmd == "patch":
        body = {}
        if a.url: body["target_hook_url"] = a.url
        if a.secret: body["headers"] = {a.header: a.secret}
        code, r = req("PATCH", f"/api/v2/webhooks/{a.id}", body); print(json.dumps({"status": code, "webhook": r}, indent=2, default=str))
    elif a.cmd == "test":
        code, r = req("POST", f"/api/v2/webhooks/{a.id}/test"); print(json.dumps({"status": code, "result": r}, indent=2, default=str))
    elif a.cmd == "delete":
        code, r = req("DELETE", f"/api/v2/webhooks/{a.id}"); print(json.dumps({"status": code, "deleted_id": a.id}, indent=2, default=str))


if __name__ == "__main__":
    main()
