// The SQLite worker pool (config/database.js) against a real, throwaway
// database file: queries run off the main thread, overload and slow queries
// turn into "unavailable" errors instead of a frozen server, and cached
// results last exactly until the database changes.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { DatabaseSync } = require('node:sqlite');

const { createPool, isUnavailable } = require(path.resolve(__dirname, '..', 'config', 'database'));

const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'db-pool-test-'));
const dbPath = path.join(dir, 'test.db');
const writer = new DatabaseSync(dbPath);
writer.exec("CREATE TABLE author (author_id TEXT PRIMARY KEY, author_name TEXT); INSERT INTO author VALUES ('A1', 'Élise'), ('A2', 'Bob');");

// A pure-SQL statement that keeps SQLite busy for roughly a second.
const SLOW_SQL = 'WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM c WHERE x < ?1) SELECT count(*) AS n FROM c';
const SLOW_ROWS = 10_000_000;

const pools = [];
const open = (options) => {
  const pool = createPool({ dbPath, ...options });
  pools.push(pool);
  return pool;
};

test.after(async () => {
  await Promise.all(pools.map((pool) => pool.close()));
  writer.close();
  try { fs.rmSync(dir, { recursive: true, force: true }); } catch { /* still locked on Windows */ }
});

test('queries return pg-shaped results, with unicode_lower available', async () => {
  const pool = open({ workers: 1 });
  const result = await pool.query('SELECT author_id FROM author WHERE unicode_lower(author_name) = ?1', ['élise']);
  assert.deepEqual(result, { rows: [{ author_id: 'A1' }], rowCount: 1 });
});

test('a slow query does not block the main thread', async () => {
  const pool = open({ workers: 1 });
  let slowDone = false;
  const slow = pool.query(SLOW_SQL, [SLOW_ROWS]).then(() => { slowDone = true; });

  const started = Date.now();
  await new Promise((resolve) => setTimeout(resolve, 50));
  assert.ok(Date.now() - started < 500, 'a timer still fires on time');
  assert.equal(slowDone, false, 'while the slow query is still running');
  await slow;
});

test('two workers run two slow queries side by side', async () => {
  const pool = open({ workers: 2 });
  const started = Date.now();
  await pool.query(SLOW_SQL, [SLOW_ROWS]);
  const one = Date.now() - started;

  const both = Date.now();
  await Promise.all([pool.query(SLOW_SQL, [SLOW_ROWS]), pool.query(SLOW_SQL, [SLOW_ROWS])]);
  assert.ok(Date.now() - both < one * 1.8, 'two at once take about as long as one');
});

test('a full queue fails fast with an "unavailable" error', async () => {
  const pool = open({ workers: 1, maxQueue: 1 });
  const running = pool.query(SLOW_SQL, [SLOW_ROWS]);
  const queued = pool.query('SELECT 1 AS one');
  await assert.rejects(pool.query('SELECT 1 AS one'), (error) => isUnavailable(error));
  await Promise.all([running, queued]);
});

test('the health check jumps the queue', async () => {
  const pool = open({ workers: 1 });
  const order = [];
  const running = pool.query(SLOW_SQL, [SLOW_ROWS]);
  const search = pool.query('SELECT 1 AS one').then(() => order.push('search'));
  const health = pool.query('SELECT 1 FROM author LIMIT 1', [], { priority: true }).then(() => order.push('health'));
  await Promise.all([running, search, health]);
  assert.deepEqual(order, ['health', 'search']);
});

test('a caller stops waiting after the timeout, and the worker recovers', async () => {
  const pool = open({ workers: 1, timeoutMs: 100 });
  await assert.rejects(pool.query(SLOW_SQL, [SLOW_ROWS]), (error) => isUnavailable(error));
  // The timed-out statement still finishes on its worker, which then serves
  // again: retry until it does, instead of guessing how long that takes.
  for (let attempt = 1; ; attempt += 1) {
    try {
      const result = await pool.query('SELECT count(*) AS n FROM author');
      assert.equal(result.rows[0].n, 2);
      break;
    } catch (error) {
      assert.ok(isUnavailable(error), error.message);
      assert.ok(attempt < 200, 'the worker never became free again');
    }
  }
});

test('cached results are reused until the database changes', async () => {
  const pool = open({ workers: 1 });
  const sql = 'SELECT random() % 1000000000 AS r';
  const first = await pool.query(sql, [], { cache: true });
  const again = await pool.query(sql, [], { cache: true });
  assert.equal(again.rows[0].r, first.rows[0].r, 'same result while nothing changed');

  writer.exec("INSERT INTO author VALUES ('A3', 'Carol')");
  const changed = await pool.query(sql, [], { cache: true });
  assert.notEqual(changed.rows[0].r, first.rows[0].r, 'recomputed after a commit');
  writer.exec("DELETE FROM author WHERE author_id = 'A3'");
});

test('a missing file is "unavailable"; a bad query is not', async () => {
  const missing = createPool({ dbPath: path.join(dir, 'missing.db'), workers: 1 });
  pools.push(missing);
  await assert.rejects(missing.query('SELECT 1 FROM author'), (error) => isUnavailable(error));

  const pool = open({ workers: 1 });
  await assert.rejects(pool.query('SELECT * FROM no_such_table'),
    (error) => !isUnavailable(error) && /no such table/.test(error.message));
});
