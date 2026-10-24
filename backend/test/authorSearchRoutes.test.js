// The real /api/authors and /api/search routes over HTTP, with the database
// and the author service replaced by recorders, to prove an invalid query is
// refused before any database work happens.
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');
const http = require('http');
const express = require('express');

const backend = path.resolve(__dirname, '..');
const stub = (relative, exports) => {
  const file = require.resolve(path.join(backend, relative));
  require.cache[file] = { id: file, filename: file, loaded: true, exports };
};

const serviceCalls = [];
stub('services/authorSearchService', {
  searchByName: async (name) => {
    serviceCalls.push(name);
    // Failures with internal details, which must never reach the client.
    if (name === 'boom-error') throw new Error('SQLITE_ERROR: no such column: a.secret_column');
    if (name === 'busy-error') throw Object.assign(new Error('database is locked'), { unavailable: true });
    return [{ id: 'A1', name }];
  },
});
stub('middleware/auth', (req, res, next) => { req.user = { id: 'u1' }; next(); });

let connects = 0;
stub('config/database', {
  // Any author lookup that reaches here finds nobody (404), which is enough:
  // these tests only care whether the database was reached at all.
  connect: async () => { connects += 1; return { query: async () => ({ rowCount: 0, rows: [] }), release() {} }; },
  query: async () => ({ rows: [] }),
  isUnavailable: (error) => Boolean(error && error.unavailable),
});

const authorsRouter = require(path.join(backend, 'routes/authors'));
const searchRouter = require(path.join(backend, 'routes/search'));

let server;
let base;
test.before(async () => {
  const app = express();
  app.use('/api/authors', authorsRouter);
  app.use('/api/search', searchRouter);
  server = http.createServer(app);
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  base = `http://127.0.0.1:${server.address().port}`;
});
test.after(() => new Promise((resolve) => server.close(resolve)));
test.beforeEach(() => { serviceCalls.length = 0; connects = 0; });

const get = async (url) => {
  const response = await fetch(base + url);
  return { status: response.status, body: await response.json() };
};
const q = (value) => encodeURIComponent(value);

test('suggestions: empty, whitespace, one character -> 400, no search', async () => {
  for (const value of ['', '   ', 'a', '  a  ']) {
    const r = await get(`/api/authors?q=${q(value)}`);
    assert.equal(r.status, 400, JSON.stringify(value));
  }
  assert.equal((await get('/api/authors')).status, 400, 'missing q');
  assert.deepEqual(serviceCalls, []);
});

test('suggestions: 201 characters -> 400 (frontend cap bypassed), no search', async () => {
  const r = await get(`/api/authors?q=${'a'.repeat(201)}`);
  assert.equal(r.status, 400);
  assert.match(r.body.message, /at most 200/);
  assert.deepEqual(serviceCalls, []);
});

test('suggestions: 2 and 200 characters are searched, trimmed', async () => {
  assert.equal((await get(`/api/authors?q=${q('  ab  ')}`)).status, 200);
  assert.equal((await get(`/api/authors?q=${'a'.repeat(200)}`)).status, 200);
  assert.deepEqual(serviceCalls, ['ab', 'a'.repeat(200)]);
});

test('suggestions: international names reach the search intact, NFC-normalized', async () => {
  for (const name of ['Jorge Martínez-Bauset', "Yi'ang Li", '王小明', 'J. R. Smith']) {
    assert.equal((await get(`/api/authors?q=${q(name)}`)).status, 200);
  }
  await get(`/api/authors?q=${q('Martínez')}`);
  assert.deepEqual(serviceCalls, ['Jorge Martínez-Bauset', "Yi'ang Li", '王小明', 'J. R. Smith', 'Martínez']);
});

test('suggestions: a repeated q parameter is a 400, not a crash', async () => {
  assert.equal((await get('/api/authors?q=ab&q=cd')).status, 400);
});

test('authenticated name search applies the same rules', async () => {
  assert.equal((await get('/api/authors/search?name=a')).status, 400);
  assert.equal((await get(`/api/authors/search?name=${'a'.repeat(201)}`)).status, 400);
  assert.equal((await get('/api/authors/search?name=ab')).status, 200);
  assert.deepEqual(serviceCalls, ['ab']);
});

test('profile lookup by name: short or oversized names never reach the database', async () => {
  assert.equal((await get('/api/search')).status, 400);
  assert.equal((await get('/api/search?author=')).status, 400);
  assert.equal((await get('/api/search?author=a')).status, 400);
  assert.equal((await get(`/api/search?author=${'a'.repeat(201)}`)).status, 400);
  assert.equal(connects, 0, 'no database connection was opened');
});

test('profile lookup: a valid name, or a well-formed id, is looked up', async () => {
  assert.equal((await get(`/api/search?author=${q("  Yi'ang Li ")}`)).status, 404); // reached the (stub) database
  assert.equal((await get('/api/search?authorId=A5050585435&author=A')).status, 404, 'with an id the name is only a label');
  assert.equal(connects, 2);
});

// Any author id, real or not, costs a full scan of author_contribution_weight,
// so a malformed one must be refused before the database.
test('malformed author ids never reach the database', async () => {
  for (const id of ['x', 'A', 'A12x', '1234', `A${'1'.repeat(21)}`, "A1' OR 1=1"]) {
    assert.equal((await get(`/api/search?authorId=${q(id)}&author=X`)).status, 400, id);
    assert.equal((await get(`/api/search/publications?authorId=${q(id)}`)).status, 400, id);
  }
  assert.equal((await get('/api/search/publications?authorId=A1&authorId=A2')).status, 400, 'repeated parameter');
  assert.equal(connects, 0, 'no database connection was opened');
});

// GET /api/authors/:id is gone (security review, finding 10): it queried
// tables openalex.db does not have and leaked the SQLite error.
test('there is no /api/authors/:id route', async () => {
  const response = await fetch(`${base}/api/authors/A5050585435`);
  assert.equal(response.status, 404);
  assert.deepEqual(serviceCalls, []);
  assert.equal(connects, 0, 'no database connection was opened');
});

// Database errors stay in the server log (security review, finding 9).
test('a failed name search does not return the database error', async () => {
  const failed = await get('/api/authors?q=boom-error');
  assert.equal(failed.status, 500);
  assert.deepEqual(failed.body, { message: 'Search failed' });

  const busy = await get('/api/authors/search?name=busy-error');
  assert.equal(busy.status, 503);
  assert.equal(busy.body.error, undefined);
  assert.doesNotMatch(JSON.stringify(busy.body), /locked/);
});
