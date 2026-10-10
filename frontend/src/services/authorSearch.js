import { API_BASE_URL } from '../config/api';

// Rules for the author-name searches on the Dashboard and in the Data Explorer.
// Mirrored on the server in backend/services/authorQuery.js.
export const AUTHOR_QUERY_MIN = 2;
export const AUTHOR_QUERY_MAX = 200;
// The delay both search boxes already used before asking for suggestions.
export const AUTHOR_SUGGESTION_DELAY_MS = 250;

export const AUTHOR_QUERY_TOO_SHORT = `Type at least ${AUTHOR_QUERY_MIN} characters of the author’s name.`;

/**
 * The query as it is sent: surrounding whitespace removed and Unicode in NFC
 * form, so "é" typed as e + a combining accent still matches the stored name.
 * Characters are deliberately NOT restricted -- real names include accents,
 * apostrophes, hyphens, periods and non-Latin scripts.
 */
export const normalizeAuthorQuery = (raw) => String(raw ?? '').trim().normalize('NFC');

export const isSearchableAuthorQuery = (query) =>
  query.length >= AUTHOR_QUERY_MIN && query.length <= AUTHOR_QUERY_MAX;

// Recent answers, so re-opening the box or returning to an earlier query does
// not ask the server again. Matching is case-insensitive on the server, so the
// key is too.
const CACHE_SIZE = 30;
const cache = new Map();

/** Suggestions for an already-normalized query. */
export async function fetchAuthorSuggestions(query, { signal } = {}) {
  const key = query.toLowerCase();
  if (cache.has(key)) {
    const cached = cache.get(key);
    cache.delete(key);
    cache.set(key, cached); // most recently used last
    return cached;
  }
  const response = await fetch(`${API_BASE_URL}/api/authors?q=${encodeURIComponent(query)}`, { signal });
  if (!response.ok) throw new Error('Author lookup failed');
  const results = await response.json();
  cache.set(key, results);
  if (cache.size > CACHE_SIZE) cache.delete(cache.keys().next().value);
  return results;
}

export const clearAuthorSuggestionCache = () => cache.clear();
