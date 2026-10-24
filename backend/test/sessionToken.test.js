// services/sessionToken.js: there is no default JWT secret any more, a weak
// one stops the server at startup, and only tokens signed with the configured
// secret (HS256) are accepted.
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');
const { spawnSync } = require('child_process');
const jwt = require('jsonwebtoken');

const SECRET = 'a-test-secret-that-is-at-least-32-characters-long';
process.env.JWT_SECRET = SECRET;

const backend = path.resolve(__dirname, '..');
const sessionToken = require(path.join(backend, 'services/sessionToken'));

test('a missing or short JWT_SECRET is refused', () => {
  assert.throws(() => sessionToken.loadSecret({}), /JWT_SECRET must be set/);
  assert.throws(() => sessionToken.loadSecret({ JWT_SECRET: 'dev-secret' }), /at least 32/);
  assert.throws(() => sessionToken.loadSecret({ JWT_SECRET: 'x'.repeat(31) }), /at least 32/);
  assert.equal(sessionToken.loadSecret({ JWT_SECRET: 'x'.repeat(32) }), 'x'.repeat(32));
});

test('only tests may run without a secret', () => {
  assert.ok(sessionToken.loadSecret({ NODE_ENV: 'test' }));
  assert.throws(() => sessionToken.loadSecret({ NODE_ENV: 'production' }), /JWT_SECRET must be set/);
});

test('the server refuses to start with a weak secret', () => {
  // dotenv never overrides a variable that is already set, so backend/.env
  // cannot replace this one.
  const run = spawnSync(process.execPath, ['server.js'], {
    cwd: backend,
    env: { ...process.env, JWT_SECRET: 'dev-secret', NODE_ENV: 'production', PORT: '0' },
    encoding: 'utf8',
    timeout: 30_000,
  });
  assert.notEqual(run.status, 0, 'the process exited with an error instead of serving');
  assert.match(run.stderr, /JWT_SECRET must be set/);
});

test('a token it signed verifies', () => {
  const payload = sessionToken.verify(sessionToken.sign({ id: 'user-1' }));
  assert.equal(payload.id, 'user-1');
});

test('a token is current only while its version matches the account', () => {
  const payload = sessionToken.verify(sessionToken.sign({ id: 'user-1', tokenVersion: 2 }));
  assert.equal(payload.tv, 2);
  assert.equal(sessionToken.isCurrent(payload, { tokenVersion: 2 }), true);
  assert.equal(sessionToken.isCurrent(payload, { tokenVersion: 3 }), false, 'ended by logout or reset');
});

test('tokens from before token versions existed stay valid until the first revocation', () => {
  const old = sessionToken.verify(jwt.sign({ id: 'user-1' }, SECRET));
  assert.equal(sessionToken.isCurrent(old, {}), true);
  assert.equal(sessionToken.isCurrent(old, { tokenVersion: 0 }), true);
  assert.equal(sessionToken.isCurrent(old, { tokenVersion: 1 }), false);
});

test("a token forged with the old default 'dev-secret' is refused", () => {
  const forged = jwt.sign({ id: 'user-1' }, 'dev-secret');
  assert.throws(() => sessionToken.verify(forged), /invalid signature/);
});

test('unsigned and other-algorithm tokens are refused', () => {
  const none = jwt.sign({ id: 'user-1' }, null, { algorithm: 'none' });
  assert.throws(() => sessionToken.verify(none));
  const hs512 = jwt.sign({ id: 'user-1' }, SECRET, { algorithm: 'HS512' });
  assert.throws(() => sessionToken.verify(hs512), /invalid algorithm/);
});
