// Exercises the real routes/library.js over HTTP. Firestore and the JWT check
// are replaced with small in-memory stand-ins so the tests need no network,
// credentials or Firebase project.
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');
const http = require('http');
const express = require('express');

// ---- In-memory Firestore ----------------------------------------------------
// Transactions run one at a time, which is the guarantee Firestore gives a
// read-modify-write transaction on a single document (it retries on conflict).
function createFakeFirestore() {
  const store = new Map();
  let queue = Promise.resolve();
  const copy = (value) => (value === undefined ? undefined : JSON.parse(JSON.stringify(value)));

  const docRef = (key) => ({
    key,
    async get() {
      const data = store.get(key);
      return { exists: data !== undefined, data: () => copy(data), get: (field) => copy(data?.[field]) };
    },
    async set(value, options = {}) {
      store.set(key, options.merge ? { ...(store.get(key) || {}), ...copy(value) } : copy(value));
    },
  });

  return {
    store,
    collection: (name) => ({ doc: (id) => docRef(`${name}/${id}`) }),
    runTransaction(fn) {
      const run = queue.then(async () => {
        const writes = [];
        const result = await fn({
          get: (ref) => ref.get(),
          set: (ref, value, options) => writes.push(() => ref.set(value, options)),
        });
        for (const write of writes) await write();
        return result;
      });
      queue = run.catch(() => {});
      return run;
    },
  };
}

const firestore = createFakeFirestore();
const backend = path.resolve(__dirname, '..');
const stub = (relative, exports) => {
  const file = require.resolve(path.join(backend, relative));
  require.cache[file] = { id: file, filename: file, loaded: true, exports };
};
stub('config/firebase', firestore);
// The real middleware verifies a JWT and loads the user; here the bearer token
// IS the user id, which is enough to test that routes scope by req.user.
stub('middleware/auth', (req, res, next) => {
  const token = (req.headers.authorization || '').replace(/^Bearer /, '');
  if (!token) return res.status(401).json({ message: 'No token provided' });
  req.user = { id: token };
  return next();
});

const libraryRouter = require(path.join(backend, 'routes/library'));

let server;
let base;
test.before(async () => {
  const app = express();
  app.use(express.json());
  app.use('/api/library', libraryRouter);
  server = http.createServer(app);
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  base = `http://127.0.0.1:${server.address().port}/api/library`;
});
test.after(() => new Promise((resolve) => server.close(resolve)));
test.beforeEach(() => firestore.store.clear());

async function call(user, method, route = '', body) {
  const response = await fetch(`${base}${route}`, {
    method,
    headers: {
      ...(user ? { Authorization: `Bearer ${user}` } : {}),
      ...(body ? { 'Content-Type': 'application/json' } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  return { status: response.status, body: await response.json() };
}

const author = (n) => ({ id: `A${1000 + n}`, name: `Author ${n}` });

test('every route requires authentication', async () => {
  for (const [method, route] of [['GET', ''], ['PUT', ''], ['POST', '/saved-authors'],
    ['DELETE', '/saved-authors/A1'], ['POST', '/recent-authors'], ['DELETE', '/recent-authors']]) {
    assert.equal((await call(null, method, route, method === 'POST' || method === 'PUT' ? {} : undefined)).status, 401, `${method} ${route}`);
  }
});

test('save, re-save, list and remove a saved author', async () => {
  const added = await call('u1', 'POST', '/saved-authors', author(1));
  assert.equal(added.status, 201);
  assert.equal(added.body.savedAuthors.length, 1);
  assert.equal(added.body.limits.savedAuthors, 100);

  const again = await call('u1', 'POST', '/saved-authors', author(1));
  assert.equal(again.status, 200, 'a duplicate save is a no-op, not an error');
  assert.equal(again.body.savedAuthors.length, 1);

  await call('u1', 'POST', '/saved-authors', author(2));
  const library = await call('u1', 'GET');
  assert.deepEqual(library.body.savedAuthors.map((a) => a.id), ['A1002', 'A1001'], 'newest first');

  const removed = await call('u1', 'DELETE', '/saved-authors/A1002');
  assert.deepEqual(removed.body.savedAuthors.map((a) => a.id), ['A1001']);
});

test('the backend refuses the 101st saved author', async () => {
  for (let i = 0; i < 100; i += 1) {
    assert.equal((await call('u1', 'POST', '/saved-authors', author(i))).status, 201);
  }
  const refused = await call('u1', 'POST', '/saved-authors', author(100));
  assert.equal(refused.status, 409);
  assert.match(refused.body.message, /up to 100 authors/);
  assert.equal((await call('u1', 'GET')).body.savedAuthors.length, 100);
});

test('concurrent saves racing for the last slot: exactly one wins', async () => {
  for (let i = 0; i < 99; i += 1) await call('u1', 'POST', '/saved-authors', author(i));
  const results = await Promise.all(
    Array.from({ length: 10 }, (_, i) => call('u1', 'POST', '/saved-authors', author(200 + i)))
  );
  const statuses = results.map((r) => r.status).sort();
  assert.equal(statuses.filter((s) => s === 201).length, 1, `statuses: ${statuses}`);
  assert.equal(statuses.filter((s) => s === 409).length, 9);
  assert.equal((await call('u1', 'GET')).body.savedAuthors.length, 100);
});

test('concurrent different saves are all kept (no lost update)', async () => {
  await Promise.all(Array.from({ length: 20 }, (_, i) => call('u1', 'POST', '/saved-authors', author(i))));
  assert.equal((await call('u1', 'GET')).body.savedAuthors.length, 20);
});

test('PUT no longer overwrites authors, so a stale device cannot undo a removal', async () => {
  await call('u1', 'POST', '/saved-authors', author(1));
  await call('u1', 'POST', '/saved-authors', author(2));
  await call('u1', 'DELETE', '/saved-authors/A1002');
  // A second device still holding the old list saves a paper with PUT.
  const stale = {
    savedAuthors: [{ ...author(1), savedAt: new Date().toISOString() }, { ...author(2), savedAt: new Date().toISOString() }],
    recentAuthors: [],
    savedPapers: [{ id: 'W1', title: 'Paper' }],
    collections: [],
  };
  assert.equal((await call('u1', 'PUT', '', stale)).status, 200);
  const library = (await call('u1', 'GET')).body;
  assert.deepEqual(library.savedAuthors.map((a) => a.id), ['A1001'], 'the removal stuck');
  assert.deepEqual(library.savedPapers.map((p) => p.id), ['W1'], 'papers still save through PUT');
});

test('history: record, revisit to top, remove one, clear', async () => {
  await call('u1', 'POST', '/recent-authors', author(1));
  await call('u1', 'POST', '/recent-authors', author(2));
  const revisit = await call('u1', 'POST', '/recent-authors', author(1));
  assert.deepEqual(revisit.body.recentAuthors.map((a) => a.id), ['A1001', 'A1002']);

  const removed = await call('u1', 'DELETE', '/recent-authors/A1002');
  assert.deepEqual(removed.body.recentAuthors.map((a) => a.id), ['A1001']);

  const cleared = await call('u1', 'DELETE', '/recent-authors');
  assert.deepEqual(cleared.body.recentAuthors, []);
  assert.deepEqual((await call('u1', 'GET')).body.recentAuthors, []);
});

test('history keeps 100 unique authors', async () => {
  for (let i = 0; i < 105; i += 1) await call('u1', 'POST', '/recent-authors', author(i));
  const history = (await call('u1', 'GET')).body.recentAuthors;
  assert.equal(history.length, 100);
  assert.equal(new Set(history.map((a) => a.id)).size, 100);
  assert.equal(history[0].id, 'A1104');
});

test('expired views are not returned', async () => {
  const old = new Date(Date.now() - 31 * 24 * 60 * 60 * 1000).toISOString();
  firestore.store.set('userLibraries/u1', {
    recentAuthors: [{ ...author(1), viewedAt: old }, { ...author(2), viewedAt: new Date().toISOString() }],
  });
  assert.deepEqual((await call('u1', 'GET')).body.recentAuthors.map((a) => a.id), ['A1002']);
});

test("users cannot see or change each other's library", async () => {
  await call('alice', 'POST', '/saved-authors', author(1));
  await call('alice', 'POST', '/recent-authors', author(1));

  // Bob sees nothing of Alice's.
  const bob = (await call('bob', 'GET')).body;
  assert.deepEqual(bob.savedAuthors, []);
  assert.deepEqual(bob.recentAuthors, []);

  // Bob's deletes and clears only touch Bob's document.
  await call('bob', 'DELETE', '/saved-authors/A1001');
  await call('bob', 'DELETE', '/recent-authors');
  // A user id in the body is ignored: the document comes from the token.
  await call('bob', 'POST', '/saved-authors', { ...author(9), userId: 'alice' });

  const alice = (await call('alice', 'GET')).body;
  assert.deepEqual(alice.savedAuthors.map((a) => a.id), ['A1001']);
  assert.deepEqual(alice.recentAuthors.map((a) => a.id), ['A1001']);
  assert.deepEqual([...firestore.store.keys()].sort(), ['userLibraries/alice', 'userLibraries/bob']);
});

test('invalid author ids are rejected with 400 and nothing is written', async () => {
  for (const body of [{}, { id: '' }, { id: 'not-an-author' }, { id: 'A1; drop' }]) {
    assert.equal((await call('u1', 'POST', '/saved-authors', body)).status, 400);
    assert.equal((await call('u1', 'POST', '/recent-authors', body)).status, 400);
  }
  assert.equal((await call('u1', 'DELETE', '/saved-authors/bogus')).status, 400);
  assert.equal(firestore.store.size, 0);
});
