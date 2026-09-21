#!/usr/bin/env python3
"""
Turn a raw Hyperagent agent export into the files in this repo.

    python3 tools/sanitize-export.py exports/agent-export.json --agent lead-management

Writes agents/<name>/agent/*, agents/<name>/guardrails.md, and every skill in
the export into the shared library under skills/doctrine/ (no code, no
credentials) or skills/clients/ (scripts and credentials). A skill that is
already in the library is overwritten and reported, so review the diff.

Reads `tools/redactions.local.json` (gitignored) for exact-string replacements
that are specific to one account: record ids, phone numbers, real names.
`tools/redactions.example.json` shows the shape. Generic secrets are caught by
the patterns below regardless of that file.

The script then refuses to write if anything that looks like a secret, a
record id, or a personal email address survives. Better to fail here than to
push it.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCAL = ROOT / "tools" / "redactions.local.json"
# One regex per line: your brand names, people, anything that must never ship.
# Gitignored, because the list itself is a list of things you do not publish.
FORBIDDEN_LOCAL = ROOT / "tools" / "forbidden.local.txt"
# Committed: generalizations (product lines, booking slugs, industry words)
# that turn one business's definitions into a template's.
NORMALIZE = ROOT / "tools" / "normalize.json"

GENERIC = [
    # Hyperagent webhook secrets quoted in skill docs
    (r"(Secret value:\*\* `)[^`]+(`)", r"\1<HYPERAGENT_WEBHOOK_SECRET>\2"),
    (r"(X-Hyperagent-Webhook-Secret: )[A-Za-z0-9_\-]{20,}", r"\1<HYPERAGENT_WEBHOOK_SECRET>"),
    # Bearer tokens and common key prefixes
    (r"Bearer [A-Za-z0-9_\-\.]{20,}", "Bearer <API_KEY>"),
    (r"\b(sk|pk|phx|phc|whsec|cal_live|cal_test|api)_[A-Za-z0-9]{20,}\b", "<API_KEY>"),
]

# Anything matching these after redaction fails the build.
FORBIDDEN = [
    (r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", "UUID (a record id)"),
    (r"\bc[a-z0-9]{24}\b", "cuid (a Hyperagent record id)"),
    (r"[\w.+-]+@(gmail|yahoo|hotmail|outlook|icloud)\.com", "personal email address"),
    # 555 numbers are documentation examples and are allowed.
    (r"\+1(?!\d{3}555)\d{10}\b", "phone number"),
    (r"\b(?=[A-Za-z0-9_\-]*\d)(?=[A-Za-z0-9_\-]*[A-Za-z])[A-Za-z0-9_\-]{40,}\b", "long token-like string"),
    (r"\bemailacct_[A-Za-z0-9]{12,}", "Instantly email account id"),
    # Prefixed opaque ids (Close's agentconfig_, lead_, cf_ and friends)
    (r"\b[a-z]{2,12}_[A-Za-z0-9]{18,}\b", "prefixed record id"),
]


def load_local() -> dict:
    if not LOCAL.exists():
        print(f"note: {LOCAL.name} not found, only generic patterns will run", file=sys.stderr)
        return {}
    return json.loads(LOCAL.read_text())


def apply_map(text: str, mapping: dict) -> str:
    # Longest strings first, so "Brand One Solutions" is replaced before "Brand One"
    # and "Owner's" before "Owner".
    for old in sorted(mapping, key=len, reverse=True):
        if old.startswith("_"):
            continue
        text = text.replace(old, mapping[old])
        # The export is JSON, so a phrase with a newline or a quote in it
        # appears escaped there. Replace that spelling too.
        esc_old, esc_new = json.dumps(old)[1:-1], json.dumps(mapping[old])[1:-1]
        if esc_old != old:
            text = text.replace(esc_old, esc_new)
    return text


def redact(text: str, local: dict) -> str:
    text = apply_map(text, local)
    if NORMALIZE.exists():
        text = apply_map(text, json.loads(NORMALIZE.read_text()))
    for pat, rep in GENERIC:
        text = re.sub(pat, rep, text)
    return text


def local_forbidden() -> list[tuple[str, str]]:
    if not FORBIDDEN_LOCAL.exists():
        print(f"note: {FORBIDDEN_LOCAL.name} not found, no branding check will run", file=sys.stderr)
        return []
    lines = [l.strip() for l in FORBIDDEN_LOCAL.read_text().splitlines()]
    return [(l, "branding or a real name") for l in lines if l and not l.startswith("#")]


def check(text: str) -> list[str]:
    problems = []
    for pat, label in FORBIDDEN + local_forbidden():
        for m in re.finditer(pat, text):
            snippet = text[max(0, m.start() - 40): m.end() + 40].replace("\n", " ")
            problems.append(f"{label}: ...{snippet}...")
    return problems


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip("\n") + "\n")


def main(export_path: str, agent: str) -> int:
    AGENT = ROOT / "agents" / agent
    raw = Path(export_path).read_text()
    clean = redact(raw, load_local())
    problems = check(clean)
    if problems:
        print("Refusing to write. Still present after redaction:", file=sys.stderr)
        for p in problems[:50]:
            print("  -", p, file=sys.stderr)
        return 1

    export = json.loads(clean)
    data = export["data"]

    # Import-safe defaults: an importer should allow their own address, not ours.
    for inv in data.get("emailInvocations", []):
        opts = inv.get("options") or {}
        if "allowedSenders" in opts:
            opts["allowedSenders"] = ["you@example.com"]

    export["exportedAt"] = "1970-01-01T00:00:00.000Z"
    write(AGENT / "agent" / f"{agent}.json", json.dumps(export, indent=2, ensure_ascii=False))
    write(AGENT / "agent" / "system-prompt.md", data["systemPrompt"])

    sched = ["# Scheduled runs\n", "Each entry is a schedule the agent runs on its own. `rrule` is an iCal recurrence.\n"]
    for s in data.get("scheduledInvocations", []):
        sched += [f"## {s['name']}\n", f"- rrule: `{s['rrule']}` ({s['timezone']})",
                  f"- delivery: {s.get('deliveryMode')}, read-only: {s.get('readOnlyMode')}, alert mode: {s.get('alertMode')}\n",
                  "```text", s["prompt"].strip(), "```\n"]
    write(AGENT / "agent" / "schedules.md", "\n".join(sched))

    hooks = ["# Webhook endpoints\n",
             "Each endpoint is a URL the agent listens on. The prompt is what the agent is told when an event lands. "
             "Secrets and endpoint ids are not part of the export; they are issued when you create the endpoint.\n"]
    for w in data.get("webhookEndpoints", []):
        hooks += [f"## {w['name']}\n", "```text", (w.get("prompt") or "").strip(), "```\n"]
    write(AGENT / "agent" / "webhooks.md", "\n".join(hooks))

    for sk in data.get("skills", []):
        is_client = sk.get("authType") != "none" or bool(sk.get("scripts"))
        d = ROOT / "skills" / ("clients" if is_client else "doctrine") / sk["name"]
        if d.exists():
            print(f"updated shared skill {d.relative_to(ROOT)} (review the diff)")
        fm = [
            "---",
            f"name: {sk['name']}",
            f"description: {json.dumps(sk.get('description') or '')}",
            f"when_to_use: {json.dumps(sk.get('whenToUse') or '')}",
            f"tags: {sk.get('tags') or '[]'}",
            f"auth: {sk.get('authType')}",
            "---",
            "",
        ]
        write(d / "SKILL.md", "\n".join(fm) + (sk.get("documentation") or sk.get("skillMdBody") or ""))
        if sk.get("credentialSchema"):
            creds = json.loads(sk["credentialSchema"])
            lines = ["# Credentials\n", "Set these on the skill after import. Values are never in the export.\n",
                     "| Key | Label | Required |", "|---|---|---|"]
            for c in creds:
                lines.append(f"| `{c.get('name')}` | {c.get('label') or ''} | {'yes' if c.get('required', True) else 'no'} |")
            write(d / "credentials.md", "\n".join(lines))
        if sk.get("scripts"):
            for sc in json.loads(sk["scripts"]):
                write(d / "scripts" / sc["filename"], sc["content"])

    # Guardrails: the safety-rules section of the prompt, on its own.
    m = re.search(r"^## Safety rules.*?(?=^## |\Z)", data["systemPrompt"], re.S | re.M)
    if m:
        write(AGENT / "guardrails.md", "# Guardrails\n\nLifted verbatim from the system prompt. "
              "These are the rules that do not bend, whatever the lead says.\n\n" + m.group(0))

    print(f"wrote agents/{agent}/ and skills/")
    return 0


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("export")
    ap.add_argument("--agent", required=True, help="folder name under agents/, e.g. lead-management")
    a = ap.parse_args()
    sys.exit(main(a.export, a.agent))
