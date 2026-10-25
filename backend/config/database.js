const path = require('path');
const { Worker } = require('node:worker_threads');

// The bibliometric data is the OpenAlex pipeline's local SQLite database,
// OpenAlex_Data_Collection/database/openalex.db -- the file the Python scripts
// in that folder keep up to date -- read where it is. OPENALEX_DB_PATH, the
// same variable those scripts read, points elsewhere; a relative value is
// resolved from backend/.
const DEFAULT_DB_PATH = path.resolve(
  __dirname, '..', '..', 'OpenAlex_Data_Collection', 'database', 'openalex.db'
);

try {
  require('node:sqlite');
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

const positive = (value, fallback) => {
  const number = Number.parseInt(value, 10);
  return Number.isFinite(number) && number > 0 ? number : fallback;
};

// Raised by the pool itself rather than by SQLite; both mean "try again later".
const QUEUE_FULL = 'ERR_DB_QUEUE_FULL';
const QUERY_TIMEOUT = 'ERR_DB_QUERY_TIMEOUT';

function poolError(code, message) {
  const error = new Error(message);
  error.code = code;
  return error;
}

/**
 * Runs queries on `workers` threads, each with its own read-only connection
 * (config/databaseWorker.js). node:sqlite is synchronous, so on the main
 * thread one slow scan stalled every request in the process; here it holds
 * one worker and the rest of the server keeps answering.
 *
 * - At most `workers` statements run at once; the rest wait in a queue.
 * - Past `maxQueue` waiting queries, new ones fail at once (503) instead of
 *   piling up behind a flood.
 * - A caller stops waiting after `timeoutMs` (503). SQLite cannot be stopped
 *   mid-statement from outside, so a running statement still finishes on its
 *   worker, which then takes the next query; a queued one is dropped.
 */
function createPool({ dbPath, workers = 2, maxQueue = 64, timeoutMs = 90_000 }) {
  const live = new Set();
  const idle = [];
  const queue = [];
  let nextId = 1;
  let closed = false;

  function spawn() {
    const worker = new Worker(path.join(__dirname, 'databaseWorker.js'), { workerData: { dbPath } });
    worker.task = null;
    live.add(worker);

    worker.on('message', ({ id, rows, error }) => {
      const { task } = worker;
      worker.task = null;
      if (task && task.id === id) task.settle(error ? Object.assign(new Error(error.message), error) : null, rows);
      release(worker);
    });

    // A crashed worker takes only its own query with it; the next query
    // that needs a thread starts a replacement.
    const lost = (error) => {
      if (worker.lost) return;
      worker.lost = true;
      live.delete(worker);
      const index = idle.indexOf(worker);
      if (index !== -1) idle.splice(index, 1);
      const { task } = worker;
      worker.task = null;
      if (task) task.settle(error || new Error('The database worker stopped unexpectedly'));
      dispatch();
    };
    worker.on('error', lost);
    worker.on('exit', () => lost());
    return worker;
  }

  // An idle worker does not keep the process alive; one with a query does.
  function release(worker) {
    if (worker.lost) return;
    worker.unref();
    idle.push(worker);
    dispatch();
  }

  function dispatch() {
    while (queue.length && !closed) {
      let worker = idle.pop();
      if (!worker) {
        if (live.size >= workers) return;
        worker = spawn();
      }
      const task = queue.shift();
      worker.task = task;
      worker.ref();
      worker.postMessage({ id: task.id, sql: task.sql, params: task.params, cache: task.cache });
    }
  }

  /**
   * Runs one statement. Same result shape as pg -- { rows, rowCount } -- so
   * the routes read results the way they always have. Placeholders are
   * SQLite's numbered ?1, ?2, ...: like PostgreSQL's $1, each may appear
   * several times.
   *
   * Options: `cache` reuses the result until the database changes (per
   * worker); `priority` jumps the queue (the health check).
   */
  function query(sql, params = [], { cache = false, priority = false } = {}) {
    if (queue.length >= maxQueue) {
      return Promise.reject(poolError(QUEUE_FULL, `More than ${maxQueue} database queries are waiting`));
    }
    return new Promise((resolve, reject) => {
      const task = { id: nextId++, sql, params, cache, settled: false };
      const timer = setTimeout(() => {
        const index = queue.indexOf(task);
        if (index !== -1) queue.splice(index, 1);
        task.settle(poolError(QUERY_TIMEOUT, `The database query did not finish within ${timeoutMs} ms`));
      }, timeoutMs);
      timer.unref();
      task.settle = (error, rows) => {
        if (task.settled) return;
        task.settled = true;
        clearTimeout(timer);
        if (error) reject(error);
        else resolve({ rows, rowCount: rows.length });
      };
      if (priority) queue.unshift(task);
      else queue.push(task);
      dispatch();
    });
  }

  // Stops every worker (tests; the server simply exits).
  function close() {
    closed = true;
    return Promise.all([...live].map((worker) => worker.terminate()));
  }

  return { query, close };
}

const dbPath = resolveDatabasePath(process.env);
const pool = createPool({
  dbPath,
  workers: positive(process.env.DB_WORKERS, 2),
  maxQueue: positive(process.env.DB_MAX_QUEUE, 64),
  timeoutMs: positive(process.env.DB_QUERY_TIMEOUT_MS, 90_000),
});

const { query } = pool;

// pg-style client for code that holds one across several queries. Every
// query goes through the shared pool, so release() has nothing to give back.
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

// The pool's own "try again later" errors.
const BUSY = {
  [QUEUE_FULL]: 'too many queries are waiting for the database',
  [QUERY_TIMEOUT]: 'a query took longer than DB_QUERY_TIMEOUT_MS',
};

const resultCode = (error) => (error && Number.isInteger(error.errcode) ? error.errcode & 0xff : null);

/** True when the error means "try again later" (HTTP 503) rather than a failed query. */
function isUnavailable(error) {
  return Boolean(error && error.code in BUSY) || resultCode(error) in UNAVAILABLE;
}

/** A one-line, log-safe reason for a database failure: the SQLite code, a hint, and the message. */
function describeDbError(error) {
  if (error && error.code in BUSY) return `[pool] ${BUSY[error.code]} (${error.message})`;
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
  createPool,
  // Where the backend reads from, for log lines.
  dbTarget: dbPath,
};
