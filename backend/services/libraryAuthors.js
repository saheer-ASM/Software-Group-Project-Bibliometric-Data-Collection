// Rules for the two author lists stored on a user's library document
// (userLibraries/{userId}): saved authors and recently viewed authors.
//
// Pure functions only -- routes/library.js applies them inside a Firestore
// transaction, so the limits hold even when two requests race.

const MAX_SAVED_AUTHORS = 100;
const MAX_RECENT_AUTHORS = 100;
const RECENT_RETENTION_DAYS = 30;
const RECENT_RETENTION_MS = RECENT_RETENTION_DAYS * 24 * 60 * 60 * 1000;

// Every author_id in the database is an OpenAlex id: "A" followed by digits.
const AUTHOR_ID_PATTERN = /^A\d{1,20}$/;

function cleanText(value, maxLength) {
  return String(value ?? '').trim().slice(0, maxLength);
}

/** A valid { id, name } from untrusted input, or null. */
function parseAuthor(input) {
  const id = cleanText(input && input.id, 32);
  if (!AUTHOR_ID_PATTERN.test(id)) return null;
  // A blank name still saves: the id identifies the author, and the profile
  // supplies the name again on the next visit.
  return { id, name: cleanText(input.name, 300) || id };
}

const time = (value) => {
  const ms = Date.parse(value);
  return Number.isFinite(ms) ? ms : NaN;
};

/**
 * Valid entries only, one per author, newest first. Where an id appears
 * twice (data written before duplicates were rejected) the newest stamp wins.
 */
function normalize(list, stampField) {
  const newest = new Map();
  (Array.isArray(list) ? list : []).forEach((raw) => {
    const author = parseAuthor(raw);
    const stamp = time(raw && raw[stampField]);
    if (!author || Number.isNaN(stamp)) return;
    const current = newest.get(author.id);
    if (!current || stamp > current.stamp) newest.set(author.id, { ...author, stamp });
  });
  return [...newest.values()]
    .sort((a, b) => b.stamp - a.stamp)
    .map(({ stamp, ...author }) => ({ ...author, [stampField]: new Date(stamp).toISOString() }));
}

/**
 * Saved authors, newest first. Never truncated here: a list that is already
 * over the limit (saved when the old cap was 500) is shown in full rather than
 * silently losing authors; addSavedAuthor() simply refuses to grow it.
 */
function normalizeSaved(list) {
  return normalize(list, 'savedAt');
}

/** Recently viewed: unexpired entries only, newest first, capped. */
function normalizeRecent(list, now = Date.now()) {
  const cutoff = now - RECENT_RETENTION_MS;
  return normalize(list, 'viewedAt')
    .filter((author) => time(author.viewedAt) >= cutoff)
    .slice(0, MAX_RECENT_AUTHORS);
}

/** { status: 'added' | 'exists' | 'limit', savedAuthors } */
function addSavedAuthor(list, author, now = Date.now()) {
  const saved = normalizeSaved(list);
  if (saved.some((item) => item.id === author.id)) return { status: 'exists', savedAuthors: saved };
  if (saved.length >= MAX_SAVED_AUTHORS) return { status: 'limit', savedAuthors: saved };
  return {
    status: 'added',
    savedAuthors: [{ ...author, savedAt: new Date(now).toISOString() }, ...saved],
  };
}

function removeSavedAuthor(list, authorId) {
  return normalizeSaved(list).filter((item) => item.id !== authorId);
}

/** Records a view: one entry per author, moved to the top, expired ones dropped. */
function recordRecentAuthor(list, author, now = Date.now()) {
  const others = normalizeRecent(list, now).filter((item) => item.id !== author.id);
  return [{ ...author, viewedAt: new Date(now).toISOString() }, ...others]
    .slice(0, MAX_RECENT_AUTHORS);
}

function removeRecentAuthor(list, authorId, now = Date.now()) {
  return normalizeRecent(list, now).filter((item) => item.id !== authorId);
}

module.exports = {
  MAX_SAVED_AUTHORS,
  MAX_RECENT_AUTHORS,
  RECENT_RETENTION_DAYS,
  AUTHOR_ID_PATTERN,
  parseAuthor,
  normalizeSaved,
  normalizeRecent,
  addSavedAuthor,
  removeSavedAuthor,
  recordRecentAuthor,
  removeRecentAuthor,
};
