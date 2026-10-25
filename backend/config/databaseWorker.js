// One SQLite connection on its own thread (see config/database.js).
//
// node:sqlite is synchronous: a statement holds whatever thread runs it until
// it finishes. Run on the main thread, a slow author scan froze every other
// request -- login, library, the health check -- for its whole duration. Here
// it only holds this worker; the main thread keeps serving.
const { parentPort, workerData } = require('node:worker_threads');
const { DatabaseSync } = require('node:sqlite');

const { dbPath } = workerData;

// Opened on first use rather than at startup, so a missing file is reported
// by the query that needed it (and /api/health) and is retried on the next one.
let db = null;

function connection() {
  if (db) return db;
  // Read-only: the backend never writes. The pipeline scripts can keep
  // updating the file meanwhile; busy_timeout makes a read wait for their
  // commit instead of failing at once.
  const opened = new DatabaseSync(dbPath, { readOnly: true });
  opened.exec('PRAGMA busy_timeout = 10000');
  // SQLite's LOWER() only folds A-Z. Name searches containing other letters
  // use this instead so they stay case-insensitive (services/authorQuery.js).
  opened.function('unicode_lower', { deterministic: true },
    (value) => (value === null ? null : String(value).toLowerCase()));
  db = opened;
  syncIndex();
  return db;
}

// The search index (services/searchIndex.js), attached as schema `idx`. It is
// opened read-only like the main database (ATTACH inherits the connection's
// flags). `wantedIndex` is what the pool last announced; `attachedIndex` what
// this connection has.
let wantedIndex = null;
let attachedIndex = null;

function syncIndex() {
  if (!db || wantedIndex === attachedIndex) return;
  try {
    if (attachedIndex) db.exec('DETACH DATABASE idx');
    attachedIndex = null;
    // Statements and cached results may refer to the previous file.
    statements.clear();
    cache.clear();
    cachedRows = 0;
    if (wantedIndex) {
      db.prepare('ATTACH DATABASE ?1 AS idx').run(wantedIndex);
      attachedIndex = wantedIndex;
    }
  } catch (error) {
    // Queries on idx then fail, and services/searchIndex.js falls back to the
    // original queries.
    console.error(`[index] a database worker could not attach the search index: ${error.message}`);
  }
}

// Prepared statements, keyed by their SQL. Route queries are assembled from a
// fixed set of fragments, so this stays small; the cap is only a safety net.
const statements = new Map();
const MAX_STATEMENTS = 500;

function prepare(sql) {
  let statement = statements.get(sql);
  if (!statement) {
    if (statements.size >= MAX_STATEMENTS) statements.clear();
    statement = connection().prepare(sql);
    statements.set(sql, statement);
  }
  return statement;
}

// Results of queries run with { cache: true }, reused until the database
// changes. PRAGMA data_version moves exactly when another connection (a
// pipeline script) commits, but its value is per connection -- which is why
// the cache lives here, next to the connection, and not in the routes.
// Least recently used first; bounded by the rows held, not the entries.
const cache = new Map();
const MAX_CACHED_ROWS = 100_000;
let cachedRows = 0;
let cacheVersion = null;

function cachedAll(sql, params) {
  const version = prepare('PRAGMA data_version').get().data_version;
  if (version !== cacheVersion) {
    cache.clear();
    cachedRows = 0;
    cacheVersion = version;
  }

  const key = `${sql}\u0000${JSON.stringify(params)}`;
  const hit = cache.get(key);
  if (hit) {
    cache.delete(key);
    cache.set(key, hit);
    return hit;
  }

  const rows = prepare(sql).all(...params);
  if (rows.length <= MAX_CACHED_ROWS) {
    cache.set(key, rows);
    cachedRows += rows.length;
    for (const [oldKey, oldRows] of cache) {
      if (cachedRows <= MAX_CACHED_ROWS) break;
      cache.delete(oldKey);
      cachedRows -= oldRows.length;
    }
  }
  return rows;
}

parentPort.on('message', ({ control, path: indexPath, id, sql, params, cache: useCache }) => {
  // Not a query: the pool announcing a (new) search index. No reply.
  if (control === 'attach') {
    wantedIndex = indexPath;
    syncIndex();
    return;
  }
  try {
    const rows = useCache ? cachedAll(sql, params) : prepare(sql).all(...params);
    parentPort.postMessage({ id, rows });
  } catch (error) {
    // Only plain fields survive postMessage; errcode is what
    // database.js uses to tell "unavailable" from "bad query".
    parentPort.postMessage({
      id,
      error: {
        message: String((error && error.message) || error),
        code: error && error.code,
        errcode: error && error.errcode,
        errstr: error && error.errstr,
      },
    });
  }
});
