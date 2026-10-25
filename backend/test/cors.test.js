// middleware/cors.js over HTTP. "nginx" is simulated: the test client is on
// loopback, which the app trusts as a proxy (like TRUST_PROXY in production),
// and sends the Host and X-Forwarded-Proto that nginx forwards from Cloudflare.
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');
const http = require('http');
const express = require('express');

const createCors = require(path.resolve(__dirname, '..', 'middleware', 'cors'));
const errorHandler = require(path.resolve(__dirname, '..', 'middleware', 'errorHandler'));

const servers = [];
async function serve({ trustProxy }) {
  const app = express();
  if (trustProxy) app.set('trust proxy', 'loopback');
  app.use(createCors(['https://partner.example']));
  app.post('/api/echo', (_req, res) => res.json({ ok: true }));
  app.use(errorHandler);
  const server = http.createServer(app);
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  servers.push(server);
  return server.address().port;
}

// http.request, because fetch() does not let a client set Host.
function post(port, headers) {
  return new Promise((resolve, reject) => {
    const req = http.request({ host: '127.0.0.1', port, path: '/api/echo', method: 'POST', headers }, (res) => {
      let body = '';
      res.on('data', (chunk) => { body += chunk; });
      res.on('end', () => resolve({ status: res.statusCode, allowOrigin: res.headers['access-control-allow-origin'], body }));
    });
    req.on('error', reject);
    req.end();
  });
}

let behindNginx;
let noProxy;
const warnings = [];
let originalWarn;
test.before(async () => {
  originalWarn = console.warn;
  console.warn = (...args) => warnings.push(args.join(' '));
  behindNginx = await serve({ trustProxy: true });
  noProxy = await serve({ trustProxy: false });
});
test.after(async () => {
  console.warn = originalWarn;
  await Promise.all(servers.map((server) => new Promise((resolve) => server.close(resolve))));
});

const viaTunnel = (host, origin) => ({ Host: host, 'X-Forwarded-Proto': 'https', Origin: origin });

test('the site itself is allowed on any tunnel address, without configuration', async () => {
  for (const host of ['precious-larry-equivalent-helping.trycloudflare.com', 'another-new-link.trycloudflare.com']) {
    const r = await post(behindNginx, viaTunnel(host, `https://${host}`));
    assert.equal(r.status, 200, host);
    assert.equal(r.allowOrigin, `https://${host}`);
  }
});

test('the site on http://localhost (nginx on port 80) is allowed', async () => {
  const r = await post(behindNginx, { Host: 'localhost', Origin: 'http://localhost' });
  assert.equal(r.status, 200);
});

test('a page on another website is refused with 403, and the origin is logged', async () => {
  warnings.length = 0;
  const r = await post(behindNginx, viaTunnel('precious-larry-equivalent-helping.trycloudflare.com', 'https://evil.example'));
  assert.equal(r.status, 403);
  assert.deepEqual(JSON.parse(r.body), { message: 'Invalid request.' });
  assert.equal(r.allowOrigin, undefined);
  assert.ok(warnings.some((line) => line.includes('https://evil.example')), 'the refused origin is in the log');
});

test('the same host on another scheme is not the same site', async () => {
  const host = 'precious-larry-equivalent-helping.trycloudflare.com';
  assert.equal((await post(behindNginx, viaTunnel(host, `http://${host}`))).status, 403);
});

test('without a trusted proxy, a client-sent X-Forwarded-Proto is ignored', async () => {
  const host = 'precious-larry-equivalent-helping.trycloudflare.com';
  // The app sees plain http, so an https Origin does not match.
  assert.equal((await post(noProxy, viaTunnel(host, `https://${host}`))).status, 403);
});

test('local development, listed origins and requests without Origin still work', async () => {
  assert.equal((await post(behindNginx, { Origin: 'http://localhost:3000' })).status, 200);
  assert.equal((await post(behindNginx, { Origin: 'https://partner.example' })).status, 200);
  assert.equal((await post(behindNginx, {})).status, 200);
});
