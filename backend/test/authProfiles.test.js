// Who may claim a profile, through the real routes/auth.js over HTTP.
// Firebase Admin is a small fake (ID tokens and Auth users kept in maps) and
// profiles live in the user store's in-memory mode.
//
// The attack (security review, finding 3): a profile exists for victim@x and no
// live Firebase account holds that address. Anyone can create an UNVERIFIED
// Firebase account for victim@x; that must not rebind or edit the profile.
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');
const http = require('http');
const express = require('express');

process.env.JWT_SECRET = 'a-test-secret-that-is-at-least-32-characters-long';

const backend = path.resolve(__dirname, '..');
const stub = (file, exports) => {
  require.cache[file] = { id: file, filename: file, loaded: true, exports };
};

const firebaseUsers = new Map(); // uid -> Firebase Auth user record
const idTokens = new Map(); // ID token -> its decoded claims
const fakeAdmin = {
  apps: [{}],
  auth: () => ({
    async verifyIdToken(idToken) {
      const decoded = idTokens.get(idToken);
      if (!decoded) throw new Error('invalid Firebase ID token');
      return decoded;
    },
    async getUser(uid) {
      const user = firebaseUsers.get(uid);
      if (!user) throw Object.assign(new Error(`No user record for ${uid}`), { code: 'auth/user-not-found' });
      return user;
    },
    async deleteUser(uid) { firebaseUsers.delete(uid); },
  }),
};
// The modules routes/auth.js loads (firebase-admin's modular API).
stub(require.resolve('firebase-admin/app', { paths: [backend] }), { getApps: () => fakeAdmin.apps });
stub(require.resolve('firebase-admin/auth', { paths: [backend] }), { getAuth: fakeAdmin.auth });
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

async function post(route, body) {
  const response = await fetch(base + route, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  return { status: response.status, body: await response.json() };
}

let counter = 0;
// A Firebase account plus an ID token for it.
function firebaseAccount({ email, verified, provider = 'password' }) {
  counter += 1;
  const uid = `uid-${counter}`;
  firebaseUsers.set(uid, { uid, email, emailVerified: verified, providerData: [{ providerId: provider }] });
  const idToken = `id-token-${counter}`;
  idTokens.set(idToken, { uid, email, email_verified: verified, firebase: { sign_in_provider: provider } });
  return { uid, idToken };
}

// A finished profile owned by `firebaseUid` (which may no longer exist in Firebase).
const profile = (email, firebaseUid) => userStore.createFirebaseUser({
  username: 'Real Owner', email, designation: 'Professor', firebaseUid, emailVerified: true,
});

// ---- the attack -------------------------------------------------------------

test('an unverified account cannot claim or edit a profile whose Firebase account is gone', async () => {
  const stored = await profile('victim1@example.com', 'deleted-uid-1');
  const attacker = firebaseAccount({ email: 'victim1@example.com', verified: false });

  for (const intent of ['register', 'signin']) {
    const r = await post('/registration-status', { idToken: attacker.idToken, intent });
    assert.equal(r.status, 409, intent);
  }
  const edit = await post('/registration/profile', {
    idToken: attacker.idToken, username: 'Attacker', designation: 'Hacker',
  });
  assert.equal(edit.status, 409);

  const after = await userStore.findById(stored.id);
  assert.equal(after.firebaseUid, 'deleted-uid-1', 'still bound to the owner');
  assert.equal(after.username, 'Real Owner', 'not edited');
  assert.equal(after.emailVerified, true, 'not marked unverified');
});

test('an unverified account cannot claim a profile another live account holds', async () => {
  const owner = firebaseAccount({ email: 'victim2@example.com', verified: true });
  const stored = await profile('victim2@example.com', owner.uid);
  const attacker = firebaseAccount({ email: 'victim2@example.com', verified: false });

  const r = await post('/registration-status', { idToken: attacker.idToken, intent: 'register' });
  assert.equal(r.status, 409);
  assert.equal((await userStore.findById(stored.id)).firebaseUid, owner.uid);
});

test('a verified account cannot take a profile another live account holds', async () => {
  const owner = firebaseAccount({ email: 'old-address@example.com', verified: true });
  const stored = await profile('shared@example.com', owner.uid);
  const other = firebaseAccount({ email: 'shared@example.com', verified: true });

  assert.equal((await post('/firebase-login', { idToken: other.idToken })).status, 409);
  assert.equal((await post('/reset-password', { idToken: other.idToken })).status, 409, 'nor through a password reset');
  assert.equal((await userStore.findById(stored.id)).firebaseUid, owner.uid);
});

// ---- legitimate flows still work -----------------------------------------------

test('a verified owner can reclaim a profile whose Firebase account is gone', async () => {
  const stored = await profile('legacy@example.com', 'deleted-uid-2');
  const owner = firebaseAccount({ email: 'legacy@example.com', verified: true });

  const r = await post('/firebase-login', { idToken: owner.idToken });
  assert.equal(r.status, 200);
  assert.ok(r.body.token);
  assert.equal((await userStore.findById(stored.id)).firebaseUid, owner.uid);
});

test('email/password registration: profile first, session only after verification', async () => {
  const account = firebaseAccount({ email: 'new-user@example.com', verified: false });
  assert.equal((await post('/register-profile', {
    idToken: account.idToken, username: 'New User', designation: 'Lecturer',
  })).status, 201);

  const pending = await post('/registration-status', { idToken: account.idToken, intent: 'register' });
  assert.equal(pending.status, 200);
  assert.equal(pending.body.status, 'COMPLETED_UNVERIFIED');
  assert.equal(pending.body.token, undefined, 'no session before verification');

  // The user clicks the verification link.
  firebaseUsers.get(account.uid).emailVerified = true;
  idTokens.get(account.idToken).email_verified = true;
  const signedIn = await post('/firebase-login', { idToken: account.idToken });
  assert.equal(signedIn.status, 200);
  assert.ok(signedIn.body.token);
});

test('a first Google sign-in on the Register page starts a registration', async () => {
  const google = firebaseAccount({ email: 'google-user@example.com', verified: true, provider: 'google.com' });
  const started = await post('/registration-status', { idToken: google.idToken, intent: 'register' });
  assert.equal(started.status, 200);
  assert.deepEqual([started.body.status, started.body.step], ['INCOMPLETE', 'profile']);

  const saved = await post('/registration/profile', {
    idToken: google.idToken, username: 'Google User', designation: 'Researcher',
  });
  assert.equal(saved.status, 200);
  assert.deepEqual([saved.body.status, saved.body.step], ['INCOMPLETE', 'password']);
});
