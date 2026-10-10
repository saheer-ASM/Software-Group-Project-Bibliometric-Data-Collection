// Rules for saved publications on a user's library document
// (userLibraries/{userId}). Pure functions; routes/library.js applies them
// inside a Firestore transaction so the limit holds when requests race.
//
// A saved paper is a REFERENCE to a publication row plus the few fields the
// My Library list shows without a request (title, year, the author it was
// saved from). The full record -- abstract, authors, citations -- is always
// read from PostgreSQL when the paper is opened, never copied here.

const MAX_SAVED_PAPERS = 200;

// Every pub_id is an OpenAlex work id ("W" + digits); every author_id is an
// OpenAlex author id ("A" + digits).
const PAPER_ID_PATTERN = /^W\d{1,20}$/;
const AUTHOR_ID_PATTERN = /^A\d{1,20}$/;

const cleanText = (value, maxLength) => String(value ?? '').trim().slice(0, maxLength);

/** A valid paper reference from untrusted input, or null. */
function parsePaper(input) {
  const id = cleanText(input && input.id, 32);
  const authorId = cleanText(input && input.authorId, 32);
  // The author is required: the details view shows the paper's metrics for
  // the author it was saved from, and cannot load without one.
  if (!PAPER_ID_PATTERN.test(id) || !AUTHOR_ID_PATTERN.test(authorId)) return null;
  const year = Number(input.publishedYear);
  return {
    id,
    title: cleanText(input.title, 1000) || 'Untitled publication',
    publishedYear: Number.isInteger(year) && year > 0 && year < 3000 ? year : null,
    authorId,
    authorName: cleanText(input.authorName, 300),
  };
}

const time = (value) => {
  const ms = Date.parse(value);
  return Number.isFinite(ms) ? ms : NaN;
};

/**
 * One entry per paper, newest saved first. Deliberately lenient with what is
 * already stored: an entry saved by an older version (no savedAt, an unusual
 * id, no author) is kept, not deleted -- only an entry with no id at all is
 * unusable. Entries without a date sort after dated ones, in stored order.
 */
function normalizeSavedPapers(list) {
  const byId = new Map();
  (Array.isArray(list) ? list : []).forEach((raw, position) => {
    const id = cleanText(raw && raw.id, 100);
    if (!id) return;
    const entry = {
      id,
      title: cleanText(raw.title, 1000),
      publishedYear: raw.publishedYear ?? null,
      authorId: cleanText(raw.authorId, 100),
      authorName: cleanText(raw.authorName, 300),
      savedAt: cleanText(raw.savedAt, 50),
    };
    const stamp = time(entry.savedAt);
    const current = byId.get(id);
    if (!current || (Number.isFinite(stamp) && !(stamp <= current.stamp))) {
      byId.set(id, { entry, stamp, position: current ? current.position : position });
    }
  });
  return [...byId.values()]
    .sort((a, b) => {
      const aDated = Number.isFinite(a.stamp);
      const bDated = Number.isFinite(b.stamp);
      if (aDated && bDated && a.stamp !== b.stamp) return b.stamp - a.stamp;
      if (aDated !== bDated) return aDated ? -1 : 1;
      return a.position - b.position;
    })
    .map(({ entry }) => entry);
}

/**
 * { status: 'added' | 'exists' | 'limit', savedPapers }. A library that is
 * already over the limit (saved when the cap was 2000) keeps every paper; it
 * just cannot grow until the user removes some.
 */
function addSavedPaper(list, paper, now = Date.now()) {
  const saved = normalizeSavedPapers(list);
  if (saved.some((item) => item.id === paper.id)) return { status: 'exists', savedPapers: saved };
  if (saved.length >= MAX_SAVED_PAPERS) return { status: 'limit', savedPapers: saved };
  return {
    status: 'added',
    savedPapers: [{ ...paper, savedAt: new Date(now).toISOString() }, ...saved],
  };
}

/** Removes the paper and drops it from every collection; the collections stay. */
function removeSavedPaper(list, collections, paperId) {
  return {
    savedPapers: normalizeSavedPapers(list).filter((item) => item.id !== paperId),
    collections: (Array.isArray(collections) ? collections : []).map((collection) => ({
      ...collection,
      paperIds: (Array.isArray(collection.paperIds) ? collection.paperIds : []).filter((id) => id !== paperId),
    })),
  };
}

module.exports = {
  MAX_SAVED_PAPERS,
  PAPER_ID_PATTERN,
  parsePaper,
  normalizeSavedPapers,
  addSavedPaper,
  removeSavedPaper,
};
