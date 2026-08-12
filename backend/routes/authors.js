const express       = require('express');
const authMiddleware = require('../middleware/auth');
const authorService  = require('../services/authorSearchService');

const router = express.Router();

// GET /api/authors/search?name=<name>
router.get('/search', authMiddleware, async (req, res) => {
  const { name } = req.query;
  if (!name || name.trim().length < 2) {
    return res.status(400).json({ message: 'Query must be at least 2 characters' });
  }

  try {
    const authors = await authorService.searchByName(name.trim());
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
