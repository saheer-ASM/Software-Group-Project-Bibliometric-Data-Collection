const express = require('express');
const pool = require('../config/database');

const router = express.Router();

const STATS_SQL = `
  SELECT
    (SELECT COUNT(*) FROM publication) AS publications,
    (SELECT COUNT(*) FROM author) AS authors,
    (
      SELECT COUNT(DISTINCT field_name)
      FROM (
        SELECT field1_name AS field_name FROM field_classification
        UNION ALL
        SELECT field2_name FROM field_classification
        UNION ALL
        SELECT field3_name FROM field_classification
      ) classified_fields
      WHERE field_name IS NOT NULL AND TRIM(field_name) <> ''
    ) AS fields
`;

// The counts scan every publication, author and field classification --
// several seconds on SQLite -- and change only when a pipeline script writes
// to the database. PRAGMA data_version changes exactly then, so the last
// result is reused until it does.
let cached = null;

// Read-only aggregate counts for the dashboard Quick Stats cards.
router.get('/', async (_req, res) => {
  try {
    const version = (await pool.query('PRAGMA data_version')).rows[0]?.data_version;
    if (!cached || cached.version !== version) {
      const result = await pool.query(STATS_SQL);
      cached = { version, stats: result.rows[0] };
    }
    return res.json(cached.stats);
  } catch (error) {
    console.error('Dashboard stats query failed:', error);
    const unavailable = pool.isUnavailable(error);
    return res.status(unavailable ? 503 : 500).json({
      message: unavailable
        ? 'The database is currently unavailable. Please try again shortly.'
        : 'Unable to read dashboard statistics from the database',
    });
  }
});

module.exports = router;
