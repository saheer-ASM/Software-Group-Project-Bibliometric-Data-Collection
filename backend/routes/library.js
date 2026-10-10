const express = require('express');
const db = require('../config/firebase');
const authMiddleware = require('../middleware/auth');
const authors = require('../services/libraryAuthors');

const router = express.Router();
const libraries = db ? db.collection('userLibraries') : null;
const emptyLibrary = () => ({ savedAuthors: [], savedPapers: [], recentAuthors: [], collections: [] });

// Sent with every library response so the interface shows the same numbers the
// server enforces.
const LIMITS = {
  savedAuthors: authors.MAX_SAVED_AUTHORS,
  recentAuthors: authors.MAX_RECENT_AUTHORS,
  recentRetentionDays: authors.RECENT_RETENTION_DAYS,
};

function cleanText(value, maxLength = 500) {
  return String(value || '').trim().slice(0, maxLength);
}

// Papers and collections: still saved as a whole with PUT, as before.
function cleanPapersAndCollections(input = {}) {
  const array = (value, limit) => (Array.isArray(value) ? value.slice(0, limit) : []);
  return {
    savedPapers: array(input.savedPapers, 2000).map((paper) => ({
      id: cleanText(paper.id, 100), title: cleanText(paper.title, 1000),
      publishedYear: paper.publishedYear ?? null, authorId: cleanText(paper.authorId, 100),
      authorName: cleanText(paper.authorName, 300), savedAt: cleanText(paper.savedAt, 50),
    })).filter((paper) => paper.id),
    collections: array(input.collections, 200).map((collection) => ({
      id: cleanText(collection.id, 100), name: cleanText(collection.name, 100),
      paperIds: [...new Set(array(collection.paperIds, 2000).map((id) => cleanText(id, 100)).filter(Boolean))],
    })).filter((collection) => collection.id && collection.name),
  };
}

function cleanLibrary(input = {}, now = Date.now()) {
  return {
    ...cleanPapersAndCollections(input),
    savedAuthors: authors.normalizeSaved(input.savedAuthors),
    // Expired views are left out of every response, so they never display.
    recentAuthors: authors.normalizeRecent(input.recentAuthors, now),
  };
}

function unavailable(res) {
  return res.status(503).json({ message: 'Library synchronization is unavailable.' });
}

function failed(res, action, error) {
  console.error(`Library request failed (${action}):`, error);
  return res.status(500).json({ message: `Unable to ${action}.` });
}

// The document is always the signed-in user's own: its id comes from the
// verified token, never from the request, so no route here can reach another
// user's library.
const userDoc = (req) => libraries.doc(String(req.user.id));

/**
 * Read-modify-write of one field in a transaction. Firestore retries the
 * callback when another request changes the document first, so two saves
 * racing for the 100th slot cannot both succeed, and neither overwrites the
 * other. `change(currentValue)` returns { value, result }; an undefined value
 * leaves the document untouched.
 */
function updateField(req, field, change) {
  const ref = userDoc(req);
  return db.runTransaction(async (transaction) => {
    const snapshot = await transaction.get(ref);
    const current = snapshot.exists ? snapshot.get(field) : undefined;
    const { value, result } = change(current);
    if (value !== undefined) {
      transaction.set(ref, { [field]: value, updatedAt: new Date().toISOString() }, { merge: true });
    }
    return result;
  });
}

router.use(authMiddleware);

router.get('/', async (req, res) => {
  if (!libraries) return unavailable(res);
  try {
    const document = await userDoc(req).get();
    const library = document.exists ? cleanLibrary(document.data()) : emptyLibrary();
    return res.json({ ...library, limits: LIMITS });
  } catch (error) {
    return failed(res, 'load your library', error);
  }
});

// Saves papers and collections. Saved and recently viewed authors are NOT
// written here any more: a whole-library save from a second tab or device
// would overwrite them -- undoing removals and dropping items saved meanwhile.
// They change only through the item routes below. Author lists in the body
// (older clients still send them) are ignored.
router.put('/', async (req, res) => {
  if (!libraries) return unavailable(res);
  try {
    const library = cleanPapersAndCollections(req.body);
    await userDoc(req).set({ ...library, updatedAt: new Date().toISOString() }, { merge: true });
    return res.json(library);
  } catch (error) {
    return failed(res, 'save your library', error);
  }
});

function readAuthor(req, res) {
  const author = authors.parseAuthor(req.body);
  if (!author) res.status(400).json({ message: 'A valid author id is required.' });
  return author;
}

function readAuthorId(req, res) {
  const id = String(req.params.authorId || '');
  if (!authors.AUTHOR_ID_PATTERN.test(id)) {
    res.status(400).json({ message: 'A valid author id is required.' });
    return null;
  }
  return id;
}

// ---- Saved authors ----------------------------------------------------------

router.post('/saved-authors', async (req, res) => {
  if (!libraries) return unavailable(res);
  const author = readAuthor(req, res);
  if (!author) return undefined;
  try {
    const outcome = await updateField(req, 'savedAuthors', (current) => {
      const result = authors.addSavedAuthor(current, author);
      // Only an actual addition is written; 'exists' and 'limit' leave the
      // document untouched.
      return { value: result.status === 'added' ? result.savedAuthors : undefined, result };
    });
    if (outcome.status === 'limit') {
      return res.status(409).json({
        message: `You can save up to ${LIMITS.savedAuthors} authors. Remove one to save another.`,
        savedAuthors: outcome.savedAuthors,
        limits: LIMITS,
      });
    }
    return res.status(outcome.status === 'added' ? 201 : 200)
      .json({ savedAuthors: outcome.savedAuthors, limits: LIMITS });
  } catch (error) {
    return failed(res, 'save this author', error);
  }
});

router.delete('/saved-authors/:authorId', async (req, res) => {
  if (!libraries) return unavailable(res);
  const authorId = readAuthorId(req, res);
  if (!authorId) return undefined;
  try {
    const savedAuthors = await updateField(req, 'savedAuthors', (current) => {
      const next = authors.removeSavedAuthor(current, authorId);
      return { value: next, result: next };
    });
    // Removing an author who is not saved is not an error: the outcome the
    // caller asked for is already true.
    return res.json({ savedAuthors, limits: LIMITS });
  } catch (error) {
    return failed(res, 'remove this author', error);
  }
});

// ---- Recently viewed authors ------------------------------------------------

router.post('/recent-authors', async (req, res) => {
  if (!libraries) return unavailable(res);
  const author = readAuthor(req, res);
  if (!author) return undefined;
  try {
    const recentAuthors = await updateField(req, 'recentAuthors', (current) => {
      const next = authors.recordRecentAuthor(current, author);
      return { value: next, result: next };
    });
    return res.json({ recentAuthors, limits: LIMITS });
  } catch (error) {
    return failed(res, 'record this author', error);
  }
});

router.delete('/recent-authors/:authorId', async (req, res) => {
  if (!libraries) return unavailable(res);
  const authorId = readAuthorId(req, res);
  if (!authorId) return undefined;
  try {
    const recentAuthors = await updateField(req, 'recentAuthors', (current) => {
      const next = authors.removeRecentAuthor(current, authorId);
      return { value: next, result: next };
    });
    return res.json({ recentAuthors, limits: LIMITS });
  } catch (error) {
    return failed(res, 'remove this author from your history', error);
  }
});

router.delete('/recent-authors', async (req, res) => {
  if (!libraries) return unavailable(res);
  try {
    await userDoc(req).set({ recentAuthors: [], updatedAt: new Date().toISOString() }, { merge: true });
    return res.json({ recentAuthors: [], limits: LIMITS });
  } catch (error) {
    return failed(res, 'clear your history', error);
  }
});

module.exports = router;
