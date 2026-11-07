// The author last shown in the Data Explorer, so that coming back to it --
// from another page, or after a refresh -- reopens that exact author (by id:
// several researchers share a name).
//
// Kept in sessionStorage: it survives a refresh but belongs to this browser
// tab only, ends when the tab closes, and is cleared at logout. The user id is
// stored with it so one account never reopens another's author.
const KEY = 'lastViewedAuthor';

/** { userId, id, name }, or null when nothing is remembered. */
export function readLastViewedAuthor() {
  try {
    const saved = JSON.parse(sessionStorage.getItem(KEY));
    const name = typeof saved?.name === 'string' ? saved.name.trim() : '';
    if (name) return { userId: String(saved.userId || ''), id: String(saved.id || ''), name };
  } catch {
    // Storage unavailable or the value damaged: nothing remembered.
  }
  return null;
}

export function saveLastViewedAuthor(userId, { id = '', name }) {
  try {
    sessionStorage.setItem(KEY, JSON.stringify({ userId: String(userId || ''), id, name }));
  } catch {
    // Storage unavailable (private mode, full): it is then remembered until a refresh only.
  }
}

export function clearLastViewedAuthor() {
  try {
    sessionStorage.removeItem(KEY);
  } catch {
    // Nothing to clear.
  }
}
