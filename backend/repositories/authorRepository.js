const pool = require('../config/database');
const { lowerFunctionFor } = require('../services/authorQuery');

async function findByName(name) {
  const lower = lowerFunctionFor(name);
  const { rows } = await pool.query(
    `SELECT a.author_id AS id, a.author_name AS name
     FROM   author a
     WHERE  INSTR(${lower}(a.author_name), ${lower}(?1)) > 0
     ORDER  BY
       CASE WHEN ${lower}(a.author_name) = ${lower}(?1) THEN 0 ELSE 1 END,
       INSTR(${lower}(a.author_name), ${lower}(?1)),
       a.author_name, a.author_id
     LIMIT  20`,
    [name]
  );
  return rows;
}

module.exports = { findByName };
