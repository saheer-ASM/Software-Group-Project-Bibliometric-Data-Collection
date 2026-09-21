const express = require('express');
const db = require('../config/firebase');
const authMiddleware = require('../middleware/auth');

const router = express.Router();
const libraries = db ? db.collection('userLibraries') : null;
const emptyLibrary = () => ({ savedAuthors: [], savedPapers: [], recentAuthors: [], collections: [] });

function cleanText(value, maxLength = 500) {
  return String(value || '').trim().slice(0, maxLength);
}

function cleanLibrary(input = {}) {
  const array = (value, limit) => (Array.isArray(value) ? value.slice(0, limit) : []);
  return {
    savedAuthors: array(input.savedAuthors, 500).map((author) => ({
      id: cleanText(author.id, 100), name: cleanText(author.name, 300), savedAt: cleanText(author.savedAt, 50),
    })).filter((author) => author.id),
    savedPapers: array(input.savedPapers, 2000).map((paper) => ({
      id: cleanText(paper.id, 100), title: cleanText(paper.title, 1000),
      publishedYear: paper.publishedYear ?? null, authorId: cleanText(paper.authorId, 100),
      authorName: cleanText(paper.authorName, 300), savedAt: cleanText(paper.savedAt, 50),
    })).filter((paper) => paper.id),
    recentAuthors: array(input.recentAuthors, 10).map((author) => ({
      id: cleanText(author.id, 100), name: cleanText(author.name, 300), viewedAt: cleanText(author.viewedAt, 50),
    })).filter((author) => author.id),
    collections: array(input.collections, 200).map((collection) => ({
      id: cleanText(collection.id, 100), name: cleanText(collection.name, 100),
      paperIds: [...new Set(array(collection.paperIds, 2000).map((id) => cleanText(id, 100)).filter(Boolean))],
    })).filter((collection) => collection.id && collection.name),
  };
}

router.use(authMiddleware);

router.get('/', async (req, res) => {
  if (!libraries) return res.status(503).json({ message: 'Library synchronization is unavailable.' });
  try {
    const document = await libraries.doc(String(req.user.id)).get();
    return res.json(document.exists ? cleanLibrary(document.data()) : emptyLibrary());
  } catch (error) {
    console.error('Library read failed:', error);
    return res.status(500).json({ message: 'Unable to load your library.' });
  }
});

router.put('/', async (req, res) => {
  if (!libraries) return res.status(503).json({ message: 'Library synchronization is unavailable.' });
  try {
    const library = cleanLibrary(req.body);
    await libraries.doc(String(req.user.id)).set({
      ...library,
      updatedAt: new Date().toISOString(),
    });
    return res.json(library);
  } catch (error) {
    console.error('Library save failed:', error);
    return res.status(500).json({ message: 'Unable to save your library.' });
  }
});

module.exports = router;
