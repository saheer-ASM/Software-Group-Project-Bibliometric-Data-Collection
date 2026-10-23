// Validation for author-name search queries, shared by /api/authors and
// /api/search. Mirrored in frontend/src/services/authorSearch.js.
//
// Runs before any database work, so a too-short or oversized query never
// reaches the database. Characters are deliberately not restricted: real author
// names include accents, apostrophes, hyphens, periods and non-Latin scripts.

const AUTHOR_QUERY_MIN = 2;
const AUTHOR_QUERY_MAX = 200;

/**
 * { value } for a usable query -- trimmed, Unicode normalized to NFC so a
 * decomposed "é" matches the stored name -- or { error } with a message for a
 * 400 response.
 */
function parseAuthorQuery(raw, { required = true } = {}) {
  // ?q=a&q=b arrives as an array; anything but one string is not a name.
  if (raw !== undefined && typeof raw !== 'string') {
    return { error: 'The author name must be a single text value.' };
  }
  const value = String(raw ?? '').trim().normalize('NFC');
  if (value.length > AUTHOR_QUERY_MAX) {
    return { error: `Author names can be at most ${AUTHOR_QUERY_MAX} characters.` };
  }
  if (required && value.length < AUTHOR_QUERY_MIN) {
    return { error: `Enter at least ${AUTHOR_QUERY_MIN} characters of the author's name.` };
  }
  return { value };
}

/**
 * The SQL function that lower-cases names for a case-insensitive match.
 * SQLite's LOWER() folds A-Z only, which is exact for an ASCII query. A query
 * with any other character uses UNICODE_LOWER (JavaScript's toLowerCase,
 * registered in config/database.js) so "élise" still finds "Élise" -- about
 * three times slower, being a JavaScript call per author row.
 */
function lowerFunctionFor(value) {
  return /^[\x00-\x7F]*$/.test(value) ? 'LOWER' : 'UNICODE_LOWER';
}

module.exports = { AUTHOR_QUERY_MIN, AUTHOR_QUERY_MAX, parseAuthorQuery, lowerFunctionFor };
