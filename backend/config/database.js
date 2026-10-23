const path = require('path');

// The bibliometric data is the OpenAlex pipeline's local SQLite database,
// OpenAlex_Data_Collection/database/openalex.db -- the file the Python scripts
// in that folder keep up to date -- read where it is. OPENALEX_DB_PATH, the
// same variable those scripts read, points elsewhere; a relative value is
// resolved from backend/.
const DEFAULT_DB_PATH = path.resolve(
  __dirname, '..', '..', 'OpenAlex_Data_Collection', 'database', 'openalex.db'
);

let DatabaseSync;
try {
  ({ DatabaseSync } = require('node:sqlite'));
} catch {
  throw new Error(
    'The backend reads the local SQLite database through node:sqlite, '
    + `which needs Node.js 22.13 or newer (this is ${process.version}).`
  );
}

function resolveDatabasePath(env) {
  const configured = String(env.OPENALEX_DB_PATH || '').trim();
  if (!configured) return DEFAULT_DB_PATH;
  return path.isAbsolute(configured) ? configured : path.resolve(__dirname, '..', configured);
}

const dbPath = resolveDatabasePath(process.env);

// One connection for the whole process. Node caches this module, so every
// route that requires it shares it. It is opened on first use rather than at
// startup, so a missing file is reported by /api/health instead of crashing
// the server, and is retried on the next query.
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
  return db;
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

/**
 * Runs one statement. Same result shape as pg -- { rows, rowCount } -- so the
 * routes read results the way they always have. Placeholders are SQLite's
 * numbered ?1, ?2, ...: like PostgreSQL's $1, each may appear several times.
 */
async function query(sql, params = []) {
  const rows = prepare(sql).all(...params);
  return { rows, rowCount: rows.length };
}

// pg-style client for code that holds one across several queries. The single
// connection serves every request, so release() has nothing to give back.
async function connect() {
  return { query, release() {} };
}

// Primary SQLite result codes (the low byte of errcode) that mean the database
// cannot be read right now, as opposed to a query being wrong.
const UNAVAILABLE = {
  5: 'the database is locked -- a pipeline script is probably writing to it', // SQLITE_BUSY
  6: 'a table is locked by another connection', // SQLITE_LOCKED
  10: 'disk I/O error while reading the database file', // SQLITE_IOERR
  14: 'cannot open the database file -- check OPENALEX_DB_PATH', // SQLITE_CANTOPEN
};

const HINTS = {
  ...UNAVAILABLE,
  11: 'the database file is damaged', // SQLITE_CORRUPT
  26: 'the file is not a SQLite database -- check OPENALEX_DB_PATH', // SQLITE_NOTADB
};

const resultCode = (error) => (error && Number.isInteger(error.errcode) ? error.errcode & 0xff : null);

/** True when the error means "try again later" (HTTP 503) rather than a failed query. */
function isUnavailable(error) {
  return resultCode(error) in UNAVAILABLE;
}

/** A one-line, log-safe reason for a database failure: the SQLite code, a hint, and the message. */
function describeDbError(error) {
  const code = resultCode(error);
  const message = String((error && error.message) || error || 'unknown error');
  const hint = HINTS[code];
  return hint ? `[SQLite ${code}] ${hint} (${message})` : message;
}

module.exports = {
  query,
  connect,
  isUnavailable,
  describeDbError,
  // Where the backend reads from, for log lines.
  dbTarget: dbPath,
};
