// The rate limiter behind a proxy, over HTTP: with trust proxy set (as
// TRUST_PROXY does in production) each forwarded client has its own counter;
// without it, everyone behind the proxy shares one.
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');
const http = require('http');
const express = require('express');

const { createRateLimit } = require(path.resolve(__dirname, '..', 'middleware', 'rateLimit'));

async function serve(configure) {
  const app = express();
  configure(app);
  app.get('/', (_req, res) => res.json({ ok: true }));
  const server = http.createServer(app);
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const base = `http://127.0.0.1:${server.address().port}`;
  const get = (forwardedFor) => fetch(base, { headers: forwardedFor ? { 'X-Forwarded-For': forwardedFor } : {} })
    .then((response) => response.status);
  return { get, close: () => new Promise((resolve) => server.close(resolve)) };
}

test('trusted proxy: each forwarded client is counted separately', async () => {
  const { get, close } = await serve((app) => {
    app.set('trust proxy', 'loopback');
    app.use(createRateLimit({ windowMs: 60_000, max: 2 }));
  });
  try {
    assert.deepEqual([await get('203.0.113.1'), await get('203.0.113.1'), await get('203.0.113.1')], [200, 200, 429]);
    // A different visitor through the same proxy is unaffected.
    assert.equal(await get('203.0.113.2'), 200);
  } finally {
    await close();
  }
});

test('untrusted proxy: X-Forwarded-For is ignored, so it cannot dodge the limit', async () => {
  const { get, close } = await serve((app) => {
    app.use(createRateLimit({ windowMs: 60_000, max: 2 }));
  });
  try {
    assert.deepEqual([await get('203.0.113.1'), await get('203.0.113.2'), await get('203.0.113.3')], [200, 200, 429]);
  } finally {
    await close();
  }
});

test('a custom key counts per account instead of per address', async () => {
  const { get, close } = await serve((app) => {
    app.use((req, _res, next) => { req.user = { id: req.get('X-Forwarded-For') }; next(); });
    app.use(createRateLimit({ windowMs: 60_000, max: 1, key: (req) => `user:${req.user.id}` }));
  });
  try {
    assert.deepEqual([await get('u1'), await get('u1'), await get('u2')], [200, 429, 200]);
  } finally {
    await close();
  }
});
