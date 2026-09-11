const express = require('express');
const pool = require('../config/database');

const router = express.Router();

// GET /api/authors?q=partial-name
router.get('/', async (req, res) => {
  const query = String(req.query.q || '').trim();
  if (query.length < 2) return res.json([]);

  try {
    const result = await pool.query(
      `SELECT author_id AS id, author_name AS name
       FROM public.author
       WHERE author_name ILIKE $1
       ORDER BY
         CASE WHEN author_name ILIKE $2 THEN 0 ELSE 1 END,
         author_name ASC
       LIMIT 8`,
      [`%${query}%`, `${query}%`]
    );
    return res.json(result.rows);
  } catch (error) {
    console.error('Author suggestions query failed:', error);
    const unavailable = ['ECONNREFUSED', 'ETIMEDOUT', 'ECONNRESET'].includes(error.code)
      || /timeout|connection terminated/i.test(error.message);
    return res.status(unavailable ? 503 : 500).json({
      message: unavailable
        ? 'Author suggestions are temporarily unavailable.'
        : 'Unable to retrieve author suggestions.',
    });
  }
});

module.exports = router;
