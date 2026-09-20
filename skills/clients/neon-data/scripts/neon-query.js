#!/usr/bin/env node
/**
 * Query a Neon Postgres database over the HTTP/WebSocket serverless driver.
 *
 * Usage:
 *   node neon-query.js "SELECT ..."            # single statement
 *   echo "SELECT ..." | node neon-query.js     # read SQL from stdin
 *   node neon-query.js --pgpass                # expose NEON_DATABASE_URL's components
 *
 * Uses @neondatabase/serverless, which tunnels Postgres over HTTPS so it works
 * from HTTP-only sandboxes (no raw TCP on 5432 required).
 *
 * Requires env var NEON_DATABASE_URL (a pooled or direct postgres:// connection
 * string, e.g. postgresql://user:pass@ep-xxx.region.aws.neon.tech/neondb?sslmode=require).
 */

const { neon } = require('@neondatabase/serverless');

// Normalize the connection string. Users often paste Neon's Connect-panel
// snippet verbatim, e.g. `psql 'postgresql://...'` or with a `postgres://`
// scheme and trailing whitespace. Strip those down to a clean URI.
function normalizeConnString(raw) {
  if (!raw) return raw;
  let s = raw.trim();
  // Strip a leading shell command prefix like "psql " (optionally with flags).
  s = s.replace(/^\s*psql\s+/, '');
  // Strip surrounding single or double quotes.
  s = s.replace(/^['"]|['"]$/g, '');
  return s;
}

const connString = normalizeConnString(process.env.NEON_DATABASE_URL);

if (process.argv.includes('--pgpass')) {
  if (!connString) {
    console.error('NEON_DATABASE_URL is not set');
    process.exit(1);
  }
  // Never print credentials; only report what is connected (host/db).
  try {
    const u = new URL(connString.replace(/^postgres(ql)?:\/\//, 'https://'));
    console.log(JSON.stringify({ host: u.hostname, database: u.pathname.replace(/^\//, ''), hasCredentials: true }));
  } catch (e) {
    console.error('Could not parse connection string:', e.message);
    process.exit(1);
  }
  process.exit(0);
}

if (!connString) {
  console.error('NEON_DATABASE_URL is not set. Run via RunWithCredentials.');
  process.exit(1);
}

// Read SQL from argv or stdin.
let sql = '';
const args = process.argv.slice(2).filter((a) => !a.startsWith('--'));
if (args.length > 0) {
  sql = args.join(' ');
} else {
  try {
    sql = require('fs').readFileSync(0, 'utf8').trim();
  } catch (e) {
    console.error('No SQL provided. Pass it as an argument or via stdin.');
    process.exit(1);
  }
}

if (!sql) {
  console.error('Empty SQL statement.');
  process.exit(1);
}

(async () => {
  const client = neon(connString);
  const start = Date.now();
  try {
    // v1.1.0+ requires either a tagged-template call or the `.query()` method for
    // conventional SQL strings with no placeholders.
    const rows = await client.query(sql);
    console.log(JSON.stringify({ rowCount: rows.length, elapsedMs: Date.now() - start, rows }, null, 2));
  } catch (err) {
    console.error('Query failed:', err.message);
    process.exit(1);
  }
})();
