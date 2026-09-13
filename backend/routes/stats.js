const express = require('express');
const pool = require('../config/database');

const router = express.Router();

// Read-only aggregate counts for the dashboard Quick Stats cards.
router.get('/', async (_req, res) => {
  try {
    const result = await pool.query(`
      SELECT
        (SELECT COUNT(*) FROM public.publication)::int AS publications,
        (SELECT COUNT(*) FROM public.author)::int AS authors,
        (
          SELECT COUNT(DISTINCT field_name)::int
          FROM (
            SELECT field1_name AS field_name FROM public.field_classification
            UNION ALL
            SELECT field2_name FROM public.field_classification
            UNION ALL
            SELECT field3_name FROM public.field_classification
          ) classified_fields
          WHERE field_name IS NOT NULL AND BTRIM(field_name) <> ''
        ) AS fields
    `);

    return res.json(result.rows[0]);
  } catch (error) {
    console.error('Dashboard stats query failed:', error);
    const unavailable = ['ECONNREFUSED', 'ETIMEDOUT', 'ECONNRESET'].includes(error.code)
      || /timeout|connection terminated/i.test(error.message);
    return res.status(unavailable ? 503 : 500).json({
      message: unavailable
        ? 'PostgreSQL is currently unavailable. Please try again shortly.'
        : 'Unable to read dashboard statistics from PostgreSQL',
    });
  }
});

module.exports = router;
