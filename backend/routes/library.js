const express = require('express');
const db = require('../config/firebase');
const authMiddleware = require('../middleware/auth');
const authors = require('../services/libraryAuthors');
const papers = require('../services/libraryPapers');

const router = express.Router();
const libraries = db ? db.collection('userLibraries') : null;
const emptyLibrary = () => ({ savedAuthors: [], savedPapers: [], recentAuthors: [], collections: [] });

// Sent with every library response so the interface shows the same numbers the
// server enforces.
const LIMITS = {
  savedAuthors: authors.MAX_SAVED_AUTHORS,
  recentAuthors: authors.MAX_RECENT_AUTHORS,
  recentRetentionDays: authors.RECENT_RETENTION_DAYS,
  savedPapers: papers.MAX_SAVED_PAPERS,
};

function cleanText(value, maxLength = 500) {
  return String(value || '').trim().slice(0, maxLength);
}

// Collections: still saved as a whole with PUT, as before.
function cleanCollections(input = {}) {
  const array = (value, limit) => (Array.isArray(value) ? value.slice(0, limit) : []);
  return array(input.collections, 200).map((collection) => ({
    id: cleanText(collection.id, 100), name: cleanText(collection.name, 100),
    paperIds: [...new Set(array(collection.paperIds, 2000).map((id) => cleanText(id, 100)).filter(Boolean))],
  })).filter((collection) => collection.id && collection.name);
}

function cleanLibrary(input = {}, now = Date.now()) {
  return {
    savedPapers: papers.normalizeSavedPapers(input.savedPapers),
    collections: cleanCollections(input),
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
 * Read-modify-write of the user's document in a transaction. Firestore retries
 * the callback when another request changes the document first, so two saves
 * racing for the last slot cannot both succeed, and neither overwrites the
 * other. `change(data)` returns { fields, result }; `fields` are merged into
 * the document, and undefined fields leave it untouched.
 */
function updateDocument(req, change) {
  const ref = userDoc(req);
  return db.runTransaction(async (transaction) => {
    const snapshot = await transaction.get(ref);
    const { fields, result } = change(snapshot.exists ? snapshot.data() : {});
    if (fields !== undefined) {
      transaction.set(ref, { ...fields, updatedAt: new Date().toISOString() }, { merge: true });
    }
    return result;
  });
}

// The single-field case the author routes use.
function updateField(req, field, change) {
  return updateDocument(req, (data) => {
    const { value, result } = change(data[field]);
    return { fields: value === undefined ? undefined : { [field]: value }, result };
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

// Saves collections (their names and which papers each holds). Saved papers
// and authors are NOT written here: a whole-library save from a second tab or
// device would overwrite them -- undoing removals, dropping items saved
// meanwhile, and bypassing the limits. They change only through the item
// routes below; those lists in the body (older clients send them) are ignored.
router.put('/', async (req, res) => {
  if (!libraries) return unavailable(res);
  try {
    const library = { collections: cleanCollections(req.body) };
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

// ---- Saved papers -----------------------------------------------------------

router.post('/saved-papers', async (req, res) => {
  if (!libraries) return unavailable(res);
  const paper = papers.parsePaper(req.body);
  if (!paper) return res.status(400).json({ message: 'A valid publication id and author id are required.' });
  try {
    const outcome = await updateDocument(req, (data) => {
      const result = papers.addSavedPaper(data.savedPapers, paper);
      return { fields: result.status === 'added' ? { savedPapers: result.savedPapers } : undefined, result };
    });
    if (outcome.status === 'limit') {
      return res.status(409).json({
        message: `You can save up to ${LIMITS.savedPapers} publications. Remove one to save another.`,
        savedPapers: outcome.savedPapers,
        limits: LIMITS,
      });
    }
    return res.status(outcome.status === 'added' ? 201 : 200)
      .json({ savedPapers: outcome.savedPapers, limits: LIMITS });
  } catch (error) {
    return failed(res, 'save this publication', error);
  }
});

router.delete('/saved-papers/:paperId', async (req, res) => {
  if (!libraries) return unavailable(res);
  // Lenient on purpose: a paper saved by an older version may have an id that
  // would not pass the check used for new saves, and it must still be removable.
  const paperId = String(req.params.paperId || '').trim().slice(0, 100);
  if (!paperId) return res.status(400).json({ message: 'A publication id is required.' });
  try {
    const next = await updateDocument(req, (data) => {
      const result = papers.removeSavedPaper(data.savedPapers, cleanCollections(data), paperId);
      return { fields: result, result };
    });
    return res.json({ ...next, limits: LIMITS });
  } catch (error) {
    return failed(res, 'remove this publication', error);
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
