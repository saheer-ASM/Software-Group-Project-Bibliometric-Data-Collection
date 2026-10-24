// middleware/errorHandler.js: errors no route handled reach the client as a
// short JSON message -- never Express's HTML page with the stack trace.
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');
const http = require('http');
const express = require('express');

const errorHandler = require(path.resolve(__dirname, '..', 'middleware', 'errorHandler'));

let server;
let base;
const logged = [];
let originalError;
test.before(async () => {
  originalError = console.error;
  console.error = (...args) => logged.push(args.join(' '));
  const app = express();
  app.use(express.json({ limit: '1kb' }));
  app.post('/echo', (req, res) => res.json(req.body));
  app.get('/crash', () => { throw new Error('SQLITE_ERROR: no such table at D:\\SoftwareProject\\backend\\routes\\x.js'); });
  app.use(errorHandler);
  server = http.createServer(app);
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  base = `http://127.0.0.1:${server.address().port}`;
});
test.after(() => {
  console.error = originalError;
  return new Promise((resolve) => server.close(resolve));
});

async function request(method, route, body) {
  const response = await fetch(base + route, {
    method, headers: body ? { 'Content-Type': 'application/json' } : {}, body,
  });
  return { status: response.status, type: response.headers.get('content-type'), text: await response.text() };
}

const leaks = (text) => /SyntaxError|SQLITE|node_modules|\\SoftwareProject|\n\s+at /.test(text);

test('a malformed JSON body gets a short JSON 400, no stack trace', async () => {
  const r = await request('POST', '/echo', '{"broken": ');
  assert.equal(r.status, 400);
  assert.match(r.type, /application\/json/);
  assert.deepEqual(JSON.parse(r.text), { message: 'The request body is not valid JSON.' });
  assert.equal(leaks(r.text), false, r.text);
});

test('an unexpected error gets a generic 500 and is logged on the server', async () => {
  const r = await request('GET', '/crash');
  assert.equal(r.status, 500);
  assert.deepEqual(JSON.parse(r.text), { message: 'Server error' });
  assert.equal(leaks(r.text), false, r.text);
  assert.ok(logged.some((line) => line.includes('SQLITE_ERROR')), 'the details stay in the server log');
});

test('other client errors keep their status with a generic message', async () => {
  const r = await request('POST', '/echo', JSON.stringify({ text: 'x'.repeat(2000) }));
  assert.equal(r.status, 413);
  assert.deepEqual(JSON.parse(r.text), { message: 'Invalid request.' });
});
