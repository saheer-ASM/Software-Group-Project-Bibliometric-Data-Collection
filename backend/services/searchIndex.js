// Keeps the search index (services/searchIndexBuilder.js) in step with
// openalex.db, and tells the routes when they may use it.
//
// - Built in a background thread at startup, unless an index of the current
//   openalex.db is already on disk. Until it is ready, the routes use their
//   original queries, which give the same results, only slower.
// - An index belongs to one version of openalex.db, identified by the file's
//   size and modification time. The moment the file changes (a pipeline script
//   wrote to it), the index is no longer used -- results never come from stale
//   data -- and a new one is built once the file has stopped changing.
// - Ready indexes are attached read-only to every database worker
//   (config/database.js), under the schema name `idx`.
//
// SEARCH_INDEX=off disables it. SEARCH_INDEX_DIR is where the files go
// (default backend/data); it must be writable, and needs about 1 GB.
const fs = require('fs');
const path = require('path');
const { Worker } = require('node:worker_threads');
const pool = require('../config/database');
const { FORMAT } = require('./searchIndexBuilder');

const ms = (name, fallback) => {
  const value = Number.parseInt(process.env[name], 10);
  return Number.isFinite(value) && value >= 0 ? value : fallback;
};
const STAT_CACHE_MS = ms('SEARCH_INDEX_STAT_CACHE_MS', 5_000);
const STABLE_MS = ms('SEARCH_INDEX_STABLE_MS', 60_000);
const CHECK_MS = ms('SEARCH_INDEX_CHECK_MS', 30_000);
const RETRY_MS = ms('SEARCH_INDEX_RETRY_MS', 10 * 60_000);

const enabled = String(process.env.SEARCH_INDEX || '').trim().toLowerCase() !== 'off';
const dir = path.resolve(__dirname, '..', process.env.SEARCH_INDEX_DIR || 'data');
const pointerFile = path.join(dir, 'search-index.json');

let state = enabled ? 'starting' : 'off'; // starting | building | ready | stale | failed | off
let current = null; // { file, fingerprint } of the attached index
let building = false;
let changedAt = 0; // when openalex.db was last seen changing
let lastFailure = 0;
let timer = null;
let statCache = { at: 0, value: null };

// Which version of openalex.db this is. A commit always rewrites the file, so
// its size and modification time change with every write.
function fingerprint() {
  const now = Date.now();
  if (now - statCache.at > STAT_CACHE_MS || statCache.value === null) {
    let value;
    try {
      const stat = fs.statSync(pool.dbTarget);
      value = `${FORMAT}:${stat.size}:${stat.mtimeMs}`;
    } catch {
      value = 'missing';
    }
    if (statCache.value !== null && value !== statCache.value) changedAt = now;
    statCache = { at: now, value };
  }
  return statCache.value;
}

/** True when the routes may query the idx tables. */
function usable() {
  if (state !== 'ready' || !current) return false;
  if (fingerprint() === current.fingerprint) return true;
  state = 'stale';
  console.log('[index] openalex.db changed: using the original queries until the search index is rebuilt');
  return false;
}

/** 'ready', 'building', 'stale', 'failed', 'starting' or 'off' (for /api/health). */
function status() {
  if (state === 'ready') usable(); // turns into 'stale' if openalex.db changed
  return state;
}

function attach(file, print) {
  pool.attachIndex(file);
  current = { file, fingerprint: print };
  state = 'ready';
}

function removeOldFiles(keep) {
  let names = [];
  try { names = fs.readdirSync(dir); } catch { return; }
  for (const name of names) {
    if (!/^search-index-\d+\.db(\.building)?$/.test(name) || path.join(dir, name) === keep) continue;
    // A worker that still has it open keeps it on Windows; the next build retries.
    try { fs.rmSync(path.join(dir, name), { force: true }); } catch { /* still open */ }
  }
}

function build() {
  if (building) return;
  building = true;
  if (state !== 'ready') state = 'building';
  const print = fingerprint();
  const file = path.join(dir, `search-index-${Date.now()}.db`);
  const temp = `${file}.building`;
  removeOldFiles(current && current.file);
  console.log('[index] building the search index from openalex.db (about a minute; searches stay available meanwhile)');

  const worker = new Worker(path.join(__dirname, 'searchIndexBuilder.js'), {
    workerData: { dbPath: pool.dbTarget, outPath: temp },
  });
  let reported = false;
  const finish = (result) => {
    if (reported) return;
    reported = true;
    building = false;
    statCache.at = 0; // read the file's state fresh
    if (!result.ok) {
      fs.rmSync(temp, { force: true });
      lastFailure = Date.now();
      if (state !== 'ready') state = 'failed';
      console.error(`[index] building the search index failed: ${result.message} (original queries stay in use; retrying later)`);
      return;
    }
    if (fingerprint() !== print) {
      // openalex.db changed while it was read: this copy may be inconsistent.
      fs.rmSync(temp, { force: true });
      console.log('[index] openalex.db changed during the build; building again once it is quiet');
      return;
    }
    fs.renameSync(temp, file);
    fs.writeFileSync(pointerFile, JSON.stringify({ file: path.basename(file), fingerprint: print }, null, 2));
    attach(file, print);
    const size = Math.round(fs.statSync(file).size / 1e6);
    console.log(`[index] search index ready: ${result.publications} author-publication rows, ${result.names} names, ${size} MB, built in ${Math.round(result.ms / 1000)} s`);
    removeOldFiles(file);
  };
  worker.on('message', finish);
  worker.on('error', (error) => finish({ ok: false, message: error.message }));
  worker.on('exit', (code) => finish({ ok: false, message: `builder stopped (exit code ${code})` }));
}

// Runs every CHECK_MS: rebuilds once openalex.db has been quiet for STABLE_MS
// after a change (a pipeline run writes many times; one build at the end).
function check() {
  if (building || state === 'off') return;
  const print = fingerprint();
  const upToDate = current && current.fingerprint === print;
  if (upToDate) return;
  if (state === 'ready') usable(); // marks it stale and says so once
  if (Date.now() - changedAt < STABLE_MS) return;
  if (state === 'failed' && Date.now() - lastFailure < RETRY_MS) return;
  build();
}

/** Called once by server.js after it starts listening. */
function start() {
  if (!enabled) {
    console.log('[index] search index disabled (SEARCH_INDEX=off): using the original queries');
    return;
  }
  try {
    fs.mkdirSync(dir, { recursive: true });
  } catch (error) {
    state = 'failed';
    console.error(`[index] cannot create ${dir}: ${error.message} (original queries stay in use)`);
    return;
  }
  // An index of this exact openalex.db from an earlier run: use it at once.
  try {
    const saved = JSON.parse(fs.readFileSync(pointerFile, 'utf8'));
    const file = path.join(dir, path.basename(saved.file));
    if (saved.fingerprint === fingerprint() && fs.existsSync(file)) {
      attach(file, saved.fingerprint);
      console.log(`[index] using the existing search index ${path.basename(file)}`);
      removeOldFiles(file);
    }
  } catch { /* none yet */ }
  if (state !== 'ready') build();
  timer = setInterval(check, CHECK_MS);
  timer.unref();
}

function stop() {
  if (timer) clearInterval(timer);
  timer = null;
}

/**
 * Runs `indexed` when the index is usable, `scan` otherwise. Each is
 * [sql, params], or null for "no indexed form" (e.g. a 2-letter name). If the
 * indexed query fails for any reason other than the database being busy,
 * the original one answers instead, so a broken index cannot break a page.
 */
async function query(run, { indexed, scan }, options = {}) {
  if (indexed && usable()) {
    try {
      return await run(indexed[0], indexed[1], options);
    } catch (error) {
      if (pool.isUnavailable(error)) throw error;
      console.error(`[index] indexed query failed, using the original query: ${error.message}`);
    }
  }
  return run(scan[0], scan[1], options);
}

module.exports = { start, stop, usable, status, query, check, build, dir };
