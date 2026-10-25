// The search index against a small throwaway "openalex.db": what the builder
// writes, that indexed name searches return exactly what the original query
// returns, that a changed database stops the index being used at once and
// gets it rebuilt, and that a broken index falls back instead of failing.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { DatabaseSync } = require('node:sqlite');

const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'search-index-test-'));
const dbPath = path.join(dir, 'openalex.db');
const indexDir = path.join(dir, 'index');

// Set before the modules below read them.
process.env.OPENALEX_DB_PATH = dbPath;
process.env.SEARCH_INDEX_DIR = indexDir;
process.env.SEARCH_INDEX_STAT_CACHE_MS = '0';
process.env.SEARCH_INDEX_STABLE_MS = '150';
process.env.SEARCH_INDEX_CHECK_MS = '50';

const writer = new DatabaseSync(dbPath);
const slots = Array.from({ length: 10 }, (_, i) => `author${i + 1}id TEXT`).join(', ');
writer.exec(`
  CREATE TABLE author (author_id TEXT PRIMARY KEY, author_name TEXT);
  CREATE TABLE publication (pub_id TEXT PRIMARY KEY, pub_title TEXT);
  CREATE TABLE author_contribution_weight (pub_id TEXT PRIMARY KEY, ${slots});
`);
const names = {
  A1: 'Élise Martin', A2: 'elise martinez', A3: "Sean O'Brien", A4: 'Jean-Luc Picard',
  A5: '王小明', A6: 'Ana_Lopez 100%', A7: 'Li Wei', A8: 'Say "Hi" Smith', A9: 'MARTIN Élodie',
};
const addAuthor = writer.prepare('INSERT INTO author VALUES (?, ?)');
for (const [id, name] of Object.entries(names)) addAuthor.run(id, name);
addAuthor.run('A10', null);
const addPublication = writer.prepare('INSERT INTO publication VALUES (?, ?)');
const addWeights = writer.prepare('INSERT INTO author_contribution_weight (pub_id, author1id, author2id, author3id) VALUES (?, ?, ?, ?)');
for (const [pub, a1, a2, a3] of [['W1', 'A1', 'A2', null], ['W2', 'A1', null, null], ['W3', 'A2', 'A2', 'A3'], ['W4', 'A3', null, null]]) {
  addPublication.run(pub, `Paper ${pub}`);
  addWeights.run(pub, a1, a2, a3);
}

const pool = require(path.resolve(__dirname, '..', 'config', 'database'));
const searchIndex = require(path.resolve(__dirname, '..', 'services', 'searchIndex'));
const { findByName } = require(path.resolve(__dirname, '..', 'repositories', 'authorRepository'));
const { build } = require(path.resolve(__dirname, '..', 'services', 'searchIndexBuilder'));
const { lowerFunctionFor } = require(path.resolve(__dirname, '..', 'services', 'authorQuery'));

async function waitFor(condition, what, timeoutMs = 15_000) {
  const started = Date.now();
  while (!condition()) {
    if (Date.now() - started > timeoutMs) throw new Error(`timed out waiting for ${what}`);
    await new Promise((resolve) => setTimeout(resolve, 25));
  }
}

// What the original (unindexed) name query returns.
async function scanByName(name) {
  const lower = lowerFunctionFor(name);
  const { rows } = await pool.query(
    `SELECT author_id AS id, author_name AS name FROM author
     WHERE INSTR(${lower}(author_name), ${lower}(?1)) > 0
     ORDER BY CASE WHEN ${lower}(author_name) = ${lower}(?1) THEN 0 ELSE 1 END,
       INSTR(${lower}(author_name), ${lower}(?1)), author_name, author_id
     LIMIT 20`, [name]);
  return rows;
}

const logs = [];
const original = { log: console.log, error: console.error };
test.before(() => {
  console.log = (...args) => logs.push(args.join(' '));
  console.error = (...args) => logs.push(args.join(' '));
});
test.after(() => {
  Object.assign(console, original);
  searchIndex.stop();
  writer.close();
  try { fs.rmSync(dir, { recursive: true, force: true }); } catch { /* still open on Windows */ }
});

test('the builder writes deduplicated author-publication pairs and every named author', () => {
  const out = path.join(dir, 'built-directly.db');
  const result = build({ dbPath, outPath: out, chunkRows: 2 });
  const index = new DatabaseSync(out, { readOnly: true });
  const pairs = index.prepare('SELECT author_id, pub_id FROM author_publication ORDER BY author_id, pub_id').all()
    .map((row) => `${row.author_id}:${row.pub_id}`);
  assert.deepEqual(pairs, ['A1:W1', 'A1:W2', 'A2:W1', 'A2:W3', 'A3:W3', 'A3:W4'], 'A2 listed twice on W3 counts once');
  assert.equal(result.names, 9, 'the author without a name is skipped');
  assert.equal(index.prepare("SELECT value FROM meta WHERE key = 'format'").get().value, '1');
  index.close();
});

test('the manager builds the index at startup, and the routes may then use it', async () => {
  assert.equal(searchIndex.usable(), false, 'not before it is built');
  searchIndex.start();
  await waitFor(() => searchIndex.status() === 'ready', 'the first build');
  assert.equal(searchIndex.usable(), true);
  assert.ok(fs.existsSync(path.join(indexDir, 'search-index.json')));
});

test('indexed name searches return exactly what the original query returns', async () => {
  await waitFor(() => searchIndex.usable(), 'the index');
  const queries = ['martin', 'MARTIN', 'élise', 'ÉLISE', "o'brien", 'jean-luc', '王小明', '小明',
    'a_l', '100%', '_', '%', 'Li', 'wei', '"hi"', 'say "', 'nobody here', 'ma'];
  for (const query of queries) {
    assert.deepEqual(await findByName(query), await scanByName(query), JSON.stringify(query));
  }
  assert.ok(!logs.some((line) => line.includes('indexed query failed')), 'answered by the index, not by the fallback');
});

test('a changed database stops the index being used at once, then it is rebuilt', async () => {
  await waitFor(() => searchIndex.usable(), 'the index');
  writer.prepare('INSERT INTO author VALUES (?, ?)').run('A11', 'Grace Hopper');

  // At once: no stale results -- the new author is found (by the original query).
  assert.equal(searchIndex.usable(), false);
  assert.deepEqual((await findByName('hopper')).map((row) => row.id), ['A11']);

  // Once the file has been quiet for a while, a new index replaces the old one.
  await waitFor(() => searchIndex.status() === 'ready', 'the rebuild');
  assert.equal(searchIndex.usable(), true);
  assert.deepEqual(await findByName('hopper'), await scanByName('hopper'));
  assert.ok(logs.some((line) => line.includes('openalex.db changed')), 'the switch is logged');
});

test('a broken index falls back to the original query instead of failing', async () => {
  await waitFor(() => searchIndex.usable(), 'the index');
  const [working] = fs.readdirSync(indexDir).filter((name) => /^search-index-\d+\.db$/.test(name));
  pool.attachIndex(path.join(indexDir, 'no-such-index.db')); // every worker loses its idx schema
  try {
    assert.deepEqual(await findByName('martin'), await scanByName('martin'));
    assert.ok(logs.some((line) => line.includes('indexed query failed, using the original query')));
  } finally {
    pool.attachIndex(path.join(indexDir, working));
  }
});
