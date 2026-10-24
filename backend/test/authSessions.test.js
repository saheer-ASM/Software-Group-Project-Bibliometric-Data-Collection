// Session revocation through the real routes/auth.js and middleware/auth.js,
// over HTTP. Firebase Admin is a small fake (ID tokens and Auth users kept in
// maps) and profiles live in the user store's in-memory mode, so no network or
// credentials are needed.
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');
const http = require('http');
const express = require('express');
const jwt = require('jsonwebtoken');

const SECRET = 'a-test-secret-that-is-at-least-32-characters-long';
process.env.JWT_SECRET = SECRET;

const backend = path.resolve(__dirname, '..');
const stub = (file, exports) => {
  require.cache[file] = { id: file, filename: file, loaded: true, exports };
};

const idTokens = new Map(); // Firebase ID token -> its decoded claims
const fakeAdmin = {
  apps: [{}],
  auth: () => ({
    async verifyIdToken(idToken) {
      const decoded = idTokens.get(idToken);
      if (!decoded) throw new Error('invalid Firebase ID token');
      return decoded;
    },
  }),
};
stub(require.resolve('firebase-admin', { paths: [backend] }), fakeAdmin);
stub(require.resolve(path.join(backend, 'config/firebase')), null);

const userStore = require(path.join(backend, 'services/firebaseUserStore'));
const authRouter = require(path.join(backend, 'routes/auth'));

let server;
let base;
test.before(async () => {
  const app = express();
  app.use(express.json());
  app.use('/api/auth', authRouter);
  server = http.createServer(app);
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  base = `http://127.0.0.1:${server.address().port}/api/auth`;
});
test.after(() => new Promise((resolve) => server.close(resolve)));

async function call(method, route, { body, token } = {}) {
  const response = await fetch(base + route, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await response.text();
  return { status: response.status, body: text ? JSON.parse(text) : null };
}

let counter = 0;
// A registered, verified account: its profile and a Firebase ID token for it.
async function account() {
  counter += 1;
  const uid = `uid-${counter}`;
  const email = `user${counter}@example.com`;
  const idToken = `id-token-${counter}`;
  idTokens.set(idToken, { uid, email, email_verified: true, firebase: { sign_in_provider: 'password' } });
  const profile = await userStore.createFirebaseUser({
    username: `User ${counter}`, email, designation: 'Researcher', firebaseUid: uid, emailVerified: true,
  });
  return { idToken, profile };
}

async function signIn(idToken) {
  const r = await call('POST', '/firebase-login', { body: { idToken } });
  assert.equal(r.status, 200);
  return r.body.token;
}

test('logout ends every session of the account', async () => {
  const { idToken } = await account();
  const laptop = await signIn(idToken);
  const phone = await signIn(idToken);
  assert.equal((await call('GET', '/profile', { token: laptop })).status, 200);
  assert.equal((await call('GET', '/profile', { token: phone })).status, 200);

  assert.equal((await call('POST', '/logout', { token: laptop })).status, 204);

  const after = await call('GET', '/profile', { token: laptop });
  assert.equal(after.status, 401, 'this session ended');
  assert.match(after.body.message, /session has ended/);
  assert.equal((await call('GET', '/profile', { token: phone })).status, 401, 'the other session ended too');

  const fresh = await signIn(idToken);
  assert.equal((await call('GET', '/profile', { token: fresh })).status, 200, 'signing in again works');
});

test('a password reset ends existing sessions and starts a new one', async () => {
  const { idToken } = await account();
  const stolen = await signIn(idToken);

  const reset = await call('POST', '/reset-password', { body: { idToken } });
  assert.equal(reset.status, 200);
  assert.equal((await call('GET', '/profile', { token: stolen })).status, 401, 'old session ended');
  assert.equal((await call('GET', '/profile', { token: reset.body.token })).status, 200, 'new session works');
});

test('logout needs a valid session', async () => {
  assert.equal((await call('POST', '/logout')).status, 401);
  const forged = jwt.sign({ id: '1' }, 'not-the-server-secret-but-long-enough-to-pass');
  assert.equal((await call('POST', '/logout', { token: forged })).status, 401);
});

test('sessions issued before this change keep working until the first logout', async () => {
  const { profile } = await account();
  // What the previous version signed: no tv claim.
  const old = jwt.sign({ id: profile.id }, SECRET, { expiresIn: '7d' });
  assert.equal((await call('GET', '/profile', { token: old })).status, 200);
  assert.equal((await call('POST', '/logout', { token: old })).status, 204);
  assert.equal((await call('GET', '/profile', { token: old })).status, 401);
});

// The old password endpoint is retired (security review, finding 6): it had no
// per-account lockout, so passwords could be guessed. Even a legacy account
// with a stored bcrypt hash and the right password gets no session.
test('the legacy password login never issues a session', async () => {
  // A legacy account, as the old createUser stored it: a bcrypt hash of
  // 'correct-horse' in the profile.
  const legacy = await userStore.createFirebaseUser({
    username: 'legacy-user', email: 'legacy-login@example.com', designation: 'Researcher', firebaseUid: 'legacy-uid',
  });
  await userStore.updateUser(legacy.id, { password: '$2a$12$2XAbT7H44guG.HWTvd5qjOsosyWmgl7P4BIDdHMl.wc/7Wy.iya0y' });
  for (const password of ['correct-horse', 'wrong-guess']) {
    const r = await call('POST', '/login', { body: { username: 'legacy-user', password } });
    assert.equal(r.status, 410, password);
    assert.equal(r.body.token, undefined);
  }
  assert.equal((await call('POST', '/login', { body: {} })).status, 410);
});

// Dead code removed (security review, finding 10). ensureFirebaseAuthUser, used
// by createUser, overwrote an existing Firebase user's password with Admin
// rights: re-wiring any of these would have been an account takeover.
test('the user store no longer offers password-setting functions', () => {
  for (const name of ['createUser', 'ensureFirebaseAuthUser', 'updatePassword', 'comparePassword', 'findOrCreateSocialUser']) {
    assert.equal(userStore[name], undefined, name);
  }
});
