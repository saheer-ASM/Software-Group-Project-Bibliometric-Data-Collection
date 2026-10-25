// Builds the search index: a SEPARATE SQLite file made from openalex.db, which
// is only read. openalex.db has no index on the ten author columns of
// author_contribution_weight or on author names, so "this author's
// publications" and name suggestions each read millions of rows. The index
// holds both as lookups:
//
//   author_publication  (author_id, pub_id), sorted by author: one lookup per
//                       author instead of a scan of every publication;
//   author_name_fts     a trigram full-text index of author names, for the
//                       "name contains ..." suggestions (3+ characters);
//   author_name_key     maps an author_name_fts row back to its author_id.
//
// openalex.db is in rollback-journal mode, where a reader keeps writers from
// committing. So the source is read in short chunks (one statement each), and
// a pipeline script writing meanwhile never waits for more than one chunk.
//
// Run in a worker thread by services/searchIndex.js; build() is exported for
// tests.
const fs = require('fs');
const { DatabaseSync } = require('node:sqlite');
const { parentPort, workerData } = require('node:worker_threads');

// Bump when the layout below changes: an index of another format is rebuilt.
const FORMAT = 1;
const AUTHOR_SLOTS = Array.from({ length: 10 }, (_, i) => `author${i + 1}id`);

function build({ dbPath, outPath, chunkRows = 50_000 }) {
  const started = Date.now();
  fs.rmSync(outPath, { force: true });
  const src = new DatabaseSync(dbPath, { readOnly: true });
  const out = new DatabaseSync(outPath);
  try {
    src.exec('PRAGMA busy_timeout = 10000');
    // A brand-new file that is thrown away if anything fails: no journal needed.
    out.exec(`
      PRAGMA journal_mode = OFF;
      PRAGMA synchronous = OFF;
      PRAGMA temp_store = FILE;
      PRAGMA cache_size = -200000;
      CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT) WITHOUT ROWID;
      CREATE TEMP TABLE author_publication_raw (author_id TEXT NOT NULL, pub_id TEXT NOT NULL);
      CREATE TABLE author_publication (
        author_id TEXT NOT NULL,
        pub_id TEXT NOT NULL,
        PRIMARY KEY (author_id, pub_id)
      ) WITHOUT ROWID;
      CREATE TABLE author_name_key (rowid INTEGER PRIMARY KEY, author_id TEXT NOT NULL);
      CREATE VIRTUAL TABLE author_name_fts USING fts5(author_name, content='', tokenize='trigram');
    `);

    // Author -> publication. Collected unsorted first, then written sorted and
    // without duplicates (an author listed twice on one paper counts once,
    // exactly as the IN (author1id, ...) scan it replaces).
    const lastPublication = src.prepare('SELECT MAX(rowid) AS last FROM author_contribution_weight').get().last || 0;
    const readPublications = src.prepare(
      `SELECT pub_id, ${AUTHOR_SLOTS.join(', ')} FROM author_contribution_weight WHERE rowid > ?1 AND rowid <= ?2`
    );
    const addPair = out.prepare('INSERT INTO author_publication_raw VALUES (?1, ?2)');
    out.exec('BEGIN');
    for (let from = 0; from < lastPublication; from += chunkRows) {
      for (const row of readPublications.all(from, from + chunkRows)) {
        for (const slot of AUTHOR_SLOTS) if (row[slot]) addPair.run(row[slot], row.pub_id);
      }
    }
    out.exec(`
      INSERT INTO author_publication
        SELECT author_id, pub_id FROM author_publication_raw GROUP BY author_id, pub_id;
      DROP TABLE author_publication_raw;
      COMMIT;
    `);

    // Author names. The row numbers of author are reused as keys.
    const lastAuthor = src.prepare('SELECT MAX(rowid) AS last FROM author').get().last || 0;
    const readAuthors = src.prepare(
      'SELECT rowid AS id, author_id, author_name FROM author WHERE rowid > ?1 AND rowid <= ?2 AND author_name IS NOT NULL'
    );
    const addKey = out.prepare('INSERT INTO author_name_key (rowid, author_id) VALUES (?1, ?2)');
    const addName = out.prepare('INSERT INTO author_name_fts (rowid, author_name) VALUES (?1, ?2)');
    out.exec('BEGIN');
    for (let from = 0; from < lastAuthor; from += chunkRows) {
      for (const row of readAuthors.all(from, from + chunkRows)) {
        addKey.run(row.id, row.author_id);
        addName.run(row.id, row.author_name);
      }
    }
    // Merges the full-text segments into one, so searches read one b-tree.
    out.exec("INSERT INTO author_name_fts (author_name_fts) VALUES ('optimize'); COMMIT");

    const counts = {
      publications: out.prepare('SELECT COUNT(*) AS n FROM author_publication').get().n,
      names: out.prepare('SELECT COUNT(*) AS n FROM author_name_key').get().n,
    };
    const addMeta = out.prepare('INSERT INTO meta VALUES (?1, ?2)');
    addMeta.run('format', String(FORMAT));
    addMeta.run('built_at', new Date().toISOString());
    return { ...counts, ms: Date.now() - started };
  } finally {
    src.close();
    out.close();
  }
}

if (parentPort && workerData && workerData.outPath) {
  try {
    parentPort.postMessage({ ok: true, ...build(workerData) });
  } catch (error) {
    parentPort.postMessage({ ok: false, message: String((error && error.message) || error) });
  }
}

module.exports = { FORMAT, build };
