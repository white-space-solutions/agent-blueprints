---
name: neon-data
description: "Query a Neon Postgres database directly over HTTP using the @neondatabase/serverless driver. Works from HTTP-only sandboxes (no raw TCP 5432). Lets the agent run arbitrary read-only or write SQL against a Neon database by authenticating with a connection string, bypassing Neon org/apikey membership requirements."
when_to_use: "When you need to query a Neon Postgres database directly from the sandbox, especially when the Neon MCP/API path is blocked by org membership or raw-TCP firewall limits."
tags: ["neon","postgres","database","sql","vercel","serverless"]
auth: api_key
---
# Neon Data

Query a Neon Postgres database directly from the agent sandbox using the
`@neondatabase/serverless` driver, which tunnels Postgres over HTTPS/WebSocket.
This bypasses both (a) the sandbox's raw-TCP firewall (no 5432 needed) and (b)
Neon's org/API-key membership requirement (authentication is a plain database
connection string).

## When to use

- Any task requiring reading or writing a Neon Postgres database: inspect tables,
  run ad-hoc queries, joins, aggregates, schema checks, data fixes.
- When a standard Postgres driver can't connect (firewalled 5432) or the Neon
  MCP/API path returns "not an organization member".
- When the operator wants direct database access rather than going through the
  Neon console/MCP.

## Prerequisites

- A valid `postgres://` (or `postgresql://`) connection string for the database.
  Pooled and direct endpoints both work. The credential may be pasted verbatim
  from Neon's Connect panel (e.g. `psql 'postgresql://...'`); the script
  normalizes it by stripping any `psql ` prefix and surrounding quotes, so no
  manual cleanup is required.

## How to run

The dependency is installed on demand (see below). Credentials are injected
automatically via RunWithCredentials, which sets `NEON_DATABASE_URL`.

Fetch the scripts and prepare:

```
FetchSkillScripts(skillName="neon-data")
```

Install the dependency once (Node is required; needs the npm registry allowlisted):

```
RunWithCredentials(skillName="neon-data", command="npm install @neondatabase/serverless --prefix /agent/workspace/skills/neon-data 2>&1 | tail -5")
```

Run a query (SQL as an argument, or pipe via stdin):

```
RunWithCredentials(skillName="neon-data", command="NODE_PATH=/agent/workspace/skills/neon-data/node_modules node /agent/workspace/skills/neon-data/neon-query.js \"SELECT * FROM table LIMIT 5\"")
```

Read SQL from a file:

```
RunWithCredentials(skillName="neon-data", command="NODE_PATH=/agent/workspace/skills/neon-data/node_modules node /agent/workspace/skills/neon-data/neon-query.js < /path/to/query.sql")
```

Verify the connection without exposing credentials:

```
RunWithCredentials(skillName="neon-data", command="NODE_PATH=/agent/workspace/skills/neon-data/node_modules node /agent/workspace/skills/neon-data/neon-query.js --pgpass")
```

Output is JSON: `{ rowCount, elapsedMs, rows }`. On error a non-zero exit with
the driver's message.

## Notes

- The driver's `neon()` client (v1.1.0+) no longer accepts a plain string call;
  use `client.query(sql)` (this script already does) or a tagged template for
  placeholders. This helper is one-statement by design for safety; for
  multi-statement or parameterized needs, extend the script.
- Never echo the connection string or credentials into chat or logs. Use
  `--pgpass` for a credentials-free connectivity check.
- Prefer read-only queries unless the operator explicitly asked for a write.
