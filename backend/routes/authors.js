const express       = require('express');
const authMiddleware = require('../middleware/auth');
const { heavyQueryLimit } = require('../middleware/rateLimit');
const authorService  = require('../services/authorSearchService');
const { parseAuthorQuery } = require('../services/authorQuery');

const router = express.Router();

// Name lookups scan the whole author table and hold a database worker while
// they run: signed-in users only, within the shared search budget.
router.use(authMiddleware, heavyQueryLimit);

// GET /api/authors?q=<name>
router.get('/', async (req, res) => {
  const query = parseAuthorQuery(req.query.q);
  if (query.error) return res.status(400).json({ message: query.error });

  try {
    const authors = await authorService.searchByName(query.value);
    res.json(authors);
  } catch (err) {
    res.status(500).json({ message: 'Search failed', error: err.message });
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
    res.status(500).json({ message: 'Search failed', error: err.message });
  }
});

// There is no GET /api/authors/:id. It read the old authors/publications schema,
// which openalex.db does not have, so every call failed and returned the SQLite
// error to the client; it also tried to write metrics to a read-only database.
// An author's profile comes from GET /api/search?authorId=.

module.exports = router;
