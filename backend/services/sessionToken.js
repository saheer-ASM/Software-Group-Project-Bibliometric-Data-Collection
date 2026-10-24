// The backend's own session token (a JWT): routes/auth.js issues it and
// middleware/auth.js checks it. Both go through here, so they always agree on
// the secret and the algorithm.
const jwt = require('jsonwebtoken');

const MIN_SECRET_LENGTH = 32;

// There is no default secret. A server started without JWT_SECRET used to sign
// with the public string 'dev-secret', so anyone could forge a session for any
// user id. Tests (NODE_ENV=test) are the only exception.
function loadSecret(env = process.env) {
  const secret = String(env.JWT_SECRET || '');
  if (secret.length >= MIN_SECRET_LENGTH) return secret;
  if (env.NODE_ENV === 'test') return 'test-only-secret-never-used-by-a-real-server';
  throw new Error(
    `JWT_SECRET must be set to a random string of at least ${MIN_SECRET_LENGTH} characters, `
    + 'different for every environment. Generate one with: '
    + "node -e \"console.log(require('crypto').randomBytes(64).toString('hex'))\""
  );
}

// Read once, when the server starts: a missing or weak secret stops it there.
const secret = loadSecret();

function sign(id) {
  return jwt.sign({ id }, secret, {
    algorithm: 'HS256',
    expiresIn: process.env.JWT_EXPIRES_IN || '7d',
  });
}

/** The token's payload; throws when it is forged, malformed or expired. */
function verify(token) {
  return jwt.verify(token, secret, { algorithms: ['HS256'] });
}

module.exports = { MIN_SECRET_LENGTH, loadSecret, sign, verify };
