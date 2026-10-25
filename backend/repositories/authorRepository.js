const pool = require('../config/database');
const { lowerFunctionFor } = require('../services/authorQuery');
const searchIndex = require('../services/searchIndex');

// A trigram index matches whole 3-character pieces, so shorter queries
// cannot use it.
const MIN_INDEXED_LENGTH = 3;

// The name as one quoted FTS5 phrase: with the trigram tokenizer that matches
// the text anywhere in a name, ignoring case. Quotes inside are doubled.
const ftsPhrase = (name) => `"${name.replace(/"/g, '""')}"`;

async function findByName(name) {
  const lower = lowerFunctionFor(name);
  // The same "contains" test and ordering either way: with the search index,
  // the trigram match only narrows down which authors are tested.
  const contains = `INSTR(${lower}(a.author_name), ${lower}(?1)) > 0`;
  const order = `ORDER  BY
       CASE WHEN ${lower}(a.author_name) = ${lower}(?1) THEN 0 ELSE 1 END,
       INSTR(${lower}(a.author_name), ${lower}(?1)),
       a.author_name, a.author_id
     LIMIT  20`;
  const { rows } = await searchIndex.query(pool.query, {
    indexed: [...name].length >= MIN_INDEXED_LENGTH ? [
      `SELECT a.author_id AS id, a.author_name AS name
       FROM   idx.author_name_fts names
       JOIN   idx.author_name_key name_key ON name_key.rowid = names.rowid
       JOIN   author a ON a.author_id = name_key.author_id
       WHERE  names.author_name_fts MATCH ?2 AND ${contains}
       ${order}`,
      [name, ftsPhrase(name)],
    ] : null,
    scan: [
      `SELECT a.author_id AS id, a.author_name AS name
       FROM   author a
       WHERE  ${contains}
       ${order}`,
      [name],
    ],
  });
  return rows;
}

module.exports = { findByName };
