const express       = require('express');
const pool          = require('../config/database');
const authMiddleware = require('../middleware/auth');
const { heavyQueryLimit } = require('../middleware/rateLimit');
const authorService  = require('../services/authorSearchService');
const { parseAuthorQuery } = require('../services/authorQuery');

const router = express.Router();

// Name lookups scan the whole author table and hold a database worker while
// they run: signed-in users only, within the shared search budget.
router.use(authMiddleware, heavyQueryLimit);

// The SQLite message stays in the server log, as in routes/search.js; the
// client gets a generic one (503 when the database is only busy or offline).
function searchFailed(res, err) {
  console.error('Author name search failed:', err);
  const unavailable = pool.isUnavailable(err);
  res.status(unavailable ? 503 : 500).json({
    message: unavailable
      ? 'The database is currently unavailable. Please try again shortly.'
      : 'Search failed',
  });
}

// GET /api/authors?q=<name>
router.get('/', async (req, res) => {
  const query = parseAuthorQuery(req.query.q);
  if (query.error) return res.status(400).json({ message: query.error });

  try {
    const authors = await authorService.searchByName(query.value);
    res.json(authors);
  } catch (err) {
    searchFailed(res, err);
  }
});

// GET /api/authors/search?name=<name>
router.get('/search', async (req, res) => {
  const query = parseAuthorQuery(req.query.name);
  if (query.error) return res.status(400).json({ message: query.error });

  try {
    const authors = await authorService.searchByName(query.value);
    res.json({ authors });
  } catch (err) {
    searchFailed(res, err);
  }
});

// There is no GET /api/authors/:id. It read the old authors/publications schema,
// which openalex.db does not have, so every call failed and returned the SQLite
// error to the client; it also tried to write metrics to a read-only database.
// An author's profile comes from GET /api/search?authorId=.

module.exports = router;
