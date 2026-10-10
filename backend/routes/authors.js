const express       = require('express');
const authMiddleware = require('../middleware/auth');
const authorService  = require('../services/authorSearchService');
const { parseAuthorQuery } = require('../services/authorQuery');

const router = express.Router();

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
router.get('/search', authMiddleware, async (req, res) => {
  const query = parseAuthorQuery(req.query.name);
  if (query.error) return res.status(400).json({ message: query.error });

  try {
    const authors = await authorService.searchByName(query.value);
    res.json({ authors });
  } catch (err) {
    res.status(500).json({ message: 'Search failed', error: err.message });
  }
});

// GET /api/authors/:id?field=<field>&year=<year>
router.get('/:id', authMiddleware, async (req, res) => {
  const { id } = req.params;
  const { field, year } = req.query;

  try {
    const result = await authorService.getAuthorDetails(id, {
      field: field || null,
      year:  year  ? parseInt(year, 10) : null,
    });

    if (!result) return res.status(404).json({ message: 'Author not found' });

    res.json(result);
  } catch (err) {
    res.status(500).json({ message: 'Failed to load author', error: err.message });
  }
});

module.exports = router;
