import { API_BASE_URL } from '../config/api';

// The limits the server enforces (backend/services/libraryAuthors.js). Mirrored
// here so a guest, whose library lives only in this browser, gets the same
// rules, and so the page can show "35/100" before the network answers.
export const MAX_SAVED_AUTHORS = 100;
export const MAX_RECENT_AUTHORS = 100;
export const RECENT_AUTHORS_PREVIEW = 20;
export const RECENT_RETENTION_DAYS = 30;
const RECENT_RETENTION_MS = RECENT_RETENTION_DAYS * 24 * 60 * 60 * 1000;

export const SAVED_AUTHOR_LIMIT_MESSAGE =
  `You can save up to ${MAX_SAVED_AUTHORS} authors. Remove one to save another.`;

const keyFor = (userId) => `scholarMetricsLibrary:${userId || 'guest'}`;
const syncWriteQueues = new Map();

const emptyLibrary = () => ({ savedAuthors: [], savedPapers: [], recentAuthors: [], collections: [] });

const authToken = () => localStorage.getItem('token');
const isSignedIn = (userId) => Boolean(userId && authToken());

const stamp = (value) => {
  const ms = Date.parse(value);
  return Number.isFinite(ms) ? ms : 0;
};

// One entry per author, newest stamp first.
function newestFirst(list, field) {
  const byId = new Map();
  (Array.isArray(list) ? list : []).forEach((item) => {
    if (!item?.id) return;
    const current = byId.get(item.id);
    if (!current || stamp(item[field]) > stamp(current[field])) byId.set(item.id, item);
  });
  return [...byId.values()].sort((a, b) => stamp(b[field]) - stamp(a[field]));
}

// History the user may see: viewed within the retention window, newest first.
function unexpired(list, now = Date.now()) {
  return newestFirst(list, 'viewedAt')
    .filter((item) => stamp(item.viewedAt) >= now - RECENT_RETENTION_MS)
    .slice(0, MAX_RECENT_AUTHORS);
}

export function getLibrary(userId) {
  try {
    const stored = { ...emptyLibrary(), ...JSON.parse(localStorage.getItem(keyFor(userId))) };
    return { ...stored, recentAuthors: unexpired(stored.recentAuthors) };
  } catch (_) {
    return emptyLibrary();
  }
}

// This browser's copy only: stores it and tells open pages, never the server.
function writeLocal(userId, library) {
  localStorage.setItem(keyFor(userId), JSON.stringify(library));
  window.dispatchEvent(new CustomEvent('research-library-changed', { detail: library }));
  return library;
}

const updateLocal = (userId, updater) => writeLocal(userId, updater(getLibrary(userId)));

export function saveLibrary(userId, library) {
  writeLocal(userId, library);
  if (isSignedIn(userId)) {
    queueRemoteLibrarySave(userId, library).catch(() => {});
  }
  return library;
}

// Papers and collections are still saved as a whole. Authors are not part of
// this request: the server keeps them through their own item requests below,
// so a save from a second tab can never undo a removal made in the first.
function queueRemoteLibrarySave(userId, library) {
  const previous = syncWriteQueues.get(userId) || Promise.resolve();
  const next = previous.catch(() => {}).then(() => fetch(`${API_BASE_URL}/api/library`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${authToken()}`,
      },
      body: JSON.stringify({ savedPapers: library.savedPapers, collections: library.collections }),
    }).then((response) => {
      if (!response.ok) throw new Error('Unable to save your library.');
      return response.json();
    }));
  syncWriteQueues.set(userId, next);
  return next.finally(() => {
    if (syncWriteQueues.get(userId) === next) syncWriteQueues.delete(userId);
  });
}

const mergeById = (remoteItems = [], localItems = []) => {
  const items = new Map();
  [...localItems, ...remoteItems].forEach((item) => item?.id && items.set(item.id, item));
  return [...items.values()];
};

function mergeLibraries(remote, local) {
  const collections = new Map();
  [...(local.collections || []), ...(remote.collections || [])].forEach((collection) => {
    if (!collection?.id) return;
    const existing = collections.get(collection.id);
    collections.set(collection.id, {
      ...collection,
      paperIds: [...new Set([...(existing?.paperIds || []), ...(collection.paperIds || [])])],
    });
  });
  return {
    // The server's lists win for authors. Merging them with this browser's
    // copy (as papers still are) would bring back an author removed on another
    // device, because this copy would still hold it.
    savedAuthors: newestFirst(remote.savedAuthors, 'savedAt'),
    savedPapers: mergeById(remote.savedPapers, local.savedPapers),
    recentAuthors: unexpired(remote.recentAuthors),
    collections: [...collections.values()],
  };
}

export async function syncLibraryFromServer(userId) {
  const token = authToken();
  if (!userId || !token) return getLibrary(userId);
  const response = await fetch(`${API_BASE_URL}/api/library`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new Error('Unable to synchronize your library.');
  const remote = await response.json();
  const merged = writeLocal(userId, mergeLibraries(remote, getLibrary(userId)));
  await queueRemoteLibrarySave(userId, merged);
  return merged;
}

export function updateLibrary(userId, updater) {
  return saveLibrary(userId, updater(getLibrary(userId)));
}

// ---- Authors: one request per change ----------------------------------------
//
// Each change is shown at once, then confirmed by the server, whose reply
// becomes this browser's copy. If the request fails the change is undone and
// the caller gets a message to show. Guests stay local, under the same limits.

async function authorRequest(method, path, body) {
  const response = await fetch(`${API_BASE_URL}/api/library${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${authToken()}`,
      ...(body ? { 'Content-Type': 'application/json' } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const payload = await response.json().catch(() => ({}));
  return { ok: response.ok, status: response.status, payload };
}

const setField = (userId, field, list) => updateLocal(userId, (library) => ({ ...library, [field]: list }));
const OFFLINE = 'Check your connection and try again.';

export async function saveAuthor(userId, author) {
  if (!author?.id) return { ok: false, saved: false, message: 'This author cannot be saved.' };
  const library = getLibrary(userId);
  if (library.savedAuthors.some((item) => item.id === author.id)) return { ok: true, saved: true };
  if (library.savedAuthors.length >= MAX_SAVED_AUTHORS) {
    return { ok: false, saved: false, limitReached: true, message: SAVED_AUTHOR_LIMIT_MESSAGE };
  }

  const entry = { id: author.id, name: author.name || author.id, savedAt: new Date().toISOString() };
  writeLocal(userId, { ...library, savedAuthors: [entry, ...library.savedAuthors] });
  if (!isSignedIn(userId)) return { ok: true, saved: true };

  const undo = () => updateLocal(userId, (current) => ({
    ...current, savedAuthors: current.savedAuthors.filter((item) => item.id !== entry.id),
  }));
  try {
    const { ok, status, payload } = await authorRequest('POST', '/saved-authors', { id: entry.id, name: entry.name });
    // The server's list is the record either way: on 409 it holds the 100 it
    // kept, which also takes this optimistic entry back out.
    if (Array.isArray(payload.savedAuthors)) setField(userId, 'savedAuthors', payload.savedAuthors);
    else if (!ok) undo();
    if (ok) return { ok: true, saved: true };
    return {
      ok: false,
      saved: false,
      limitReached: status === 409,
      message: payload.message || 'Could not save this author. Please try again.',
    };
  } catch (_) {
    undo();
    return { ok: false, saved: false, message: `Could not save this author. ${OFFLINE}` };
  }
}

export async function removeSavedAuthor(userId, authorId) {
  const library = getLibrary(userId);
  const removed = library.savedAuthors.find((item) => item.id === authorId);
  if (!removed) return { ok: true, saved: false };
  writeLocal(userId, { ...library, savedAuthors: library.savedAuthors.filter((item) => item.id !== authorId) });
  if (!isSignedIn(userId)) return { ok: true, saved: false };

  const undo = () => updateLocal(userId, (current) => ({
    ...current, savedAuthors: newestFirst([removed, ...current.savedAuthors], 'savedAt'),
  }));
  try {
    const { ok, payload } = await authorRequest('DELETE', `/saved-authors/${encodeURIComponent(authorId)}`);
    if (ok && Array.isArray(payload.savedAuthors)) setField(userId, 'savedAuthors', payload.savedAuthors);
    if (ok) return { ok: true, saved: false };
    undo();
    return { ok: false, saved: true, message: payload.message || 'Could not remove this author. Please try again.' };
  } catch (_) {
    undo();
    return { ok: false, saved: true, message: `Could not remove this author. ${OFFLINE}` };
  }
}

/** Save if not saved, else remove. Resolves to { ok, saved, message? }. */
export function toggleSavedAuthor(userId, author) {
  return getLibrary(userId).savedAuthors.some((item) => item.id === author?.id)
    ? removeSavedAuthor(userId, author.id)
    : saveAuthor(userId, author);
}

/** Called whenever an author profile opens. Never reports failure to the user. */
export async function recordRecentAuthor(userId, author) {
  if (!author?.id) return;
  updateLocal(userId, (library) => ({
    ...library,
    recentAuthors: unexpired([
      { id: author.id, name: author.name || author.id, viewedAt: new Date().toISOString() },
      ...library.recentAuthors.filter((item) => item.id !== author.id),
    ]),
  }));
  if (!isSignedIn(userId)) return;
  try {
    const { ok, payload } = await authorRequest('POST', '/recent-authors', { id: author.id, name: author.name });
    if (ok && Array.isArray(payload.recentAuthors)) setField(userId, 'recentAuthors', payload.recentAuthors);
  } catch (_) {
    // History is a convenience: the next library sync reconciles it.
  }
}

export async function removeRecentAuthor(userId, authorId) {
  const library = getLibrary(userId);
  const removed = library.recentAuthors.find((item) => item.id === authorId);
  if (!removed) return { ok: true };
  writeLocal(userId, { ...library, recentAuthors: library.recentAuthors.filter((item) => item.id !== authorId) });
  if (!isSignedIn(userId)) return { ok: true };

  const undo = () => updateLocal(userId, (current) => ({
    ...current, recentAuthors: unexpired([removed, ...current.recentAuthors]),
  }));
  try {
    const { ok, payload } = await authorRequest('DELETE', `/recent-authors/${encodeURIComponent(authorId)}`);
    if (ok && Array.isArray(payload.recentAuthors)) setField(userId, 'recentAuthors', payload.recentAuthors);
    if (ok) return { ok: true };
    undo();
    return { ok: false, message: payload.message || 'Could not remove this author from your history.' };
  } catch (_) {
    undo();
    return { ok: false, message: `Could not remove this author from your history. ${OFFLINE}` };
  }
}

export async function clearRecentAuthors(userId) {
  const previous = getLibrary(userId).recentAuthors;
  setField(userId, 'recentAuthors', []);
  if (!isSignedIn(userId)) return { ok: true };
  try {
    const { ok, payload } = await authorRequest('DELETE', '/recent-authors');
    if (ok) return { ok: true };
    setField(userId, 'recentAuthors', previous);
    return { ok: false, message: payload.message || 'Could not clear your history. Please try again.' };
  } catch (_) {
    setField(userId, 'recentAuthors', previous);
    return { ok: false, message: `Could not clear your history. ${OFFLINE}` };
  }
}

export function toggleSavedPaper(userId, paper) {
  return updateLibrary(userId, (library) => ({
    ...library,
    savedPapers: library.savedPapers.some((item) => item.id === paper.id)
      ? library.savedPapers.filter((item) => item.id !== paper.id)
      : [{ ...paper, savedAt: new Date().toISOString() }, ...library.savedPapers]
  }));
}

export function savePaperToCollection(userId, paper, collectionId, newCollectionName = '') {
  return updateLibrary(userId, (library) => {
    let collections = library.collections;
    let targetId = collectionId;
    const name = newCollectionName.trim();
    if (name) {
      targetId = `collection-${Date.now()}`;
      collections = [...collections, { id: targetId, name, paperIds: [] }];
    }
    collections = collections.map((collection) => ({
      ...collection,
      paperIds: collection.id === targetId
        ? [...new Set([...collection.paperIds, paper.id])]
        : collection.paperIds.filter((id) => id !== paper.id)
    }));
    return {
      ...library,
      collections,
      savedPapers: library.savedPapers.some((item) => item.id === paper.id)
        ? library.savedPapers
        : [{ ...paper, savedAt: new Date().toISOString() }, ...library.savedPapers]
    };
  });
}

export function downloadAuthorPdf(data) {
  const clean = (value) => String(value ?? '').replace(/[^\x20-\x7E]/g, ' ').replace(/[()\\]/g, '\\$&');
  const wrap = (text, width = 72) => {
    const words = clean(text).split(/\s+/); const lines = []; let line = '';
    words.forEach((word) => { if (`${line} ${word}`.trim().length > width) { if (line) lines.push(line); line = word; } else line = `${line} ${word}`.trim(); });
    if (line) lines.push(line); return lines;
  };
  const text = (x, y, size, value, color = '0.04 0.15 0.29') => `${color} rg BT /F1 ${size} Tf ${x} ${y} Td (${clean(value)}) Tj ET`;
  const rect = (x, y, w, h, color) => `${color} rg ${x} ${y} ${w} ${h} re f`;
  const line = (x1, y1, x2, y2, color = '0.86 0.90 0.94') => `${color} RG ${x1} ${y1} m ${x2} ${y2} l S`;
  const papers = data.publications || [];
  const pageCount = Math.max(1, Math.ceil(papers.length / 8));
  const streams = Array.from({ length: pageCount }, (_, pageIndex) => {
    const commands = [rect(0, 0, 612, 842, '0.97 0.98 0.99'), rect(0, 742, 612, 100, '0.03 0.15 0.29'), rect(0, 736, 612, 6, '0.78 0.60 0.24')];
    commands.push(text(42, 803, 20, 'NmIndex', '1 1 1'), text(42, 780, 10, 'AUTHOR SUMMARY REPORT', '0.90 0.72 0.31'));
    commands.push(text(500, 803, 9, `Page ${pageIndex + 1} of ${pageCount}`, '0.82 0.88 0.92'));
    if (pageIndex === 0) {
      commands.push(text(42, 698, 20, data.author), text(42, 675, 10, `Research profile  |  ${data.authorId || 'ID unavailable'}`, '0.33 0.42 0.53'));
      const metrics = [['PUBLICATIONS', data.totalPublications], ['CITATIONS', data.totalCitations], ['H-INDEX', data.hIndex], ['NM-INDEX', data.nmIndex], ['C-SCORE', Number(data.cScore || 0).toFixed(3)], ['ADJUSTED CITATIONS', Number(data.totalAdjustedCitations || 0).toFixed(3)]];
      metrics.forEach(([label, value], index) => { const x = 42 + (index % 3) * 176; const y = 598 - Math.floor(index / 3) * 86; commands.push(rect(x, y, 160, 68, '0.92 0.95 0.97'), text(x + 14, y + 43, 8, label, '0.33 0.42 0.53'), text(x + 14, y + 17, 17, value)); });
      commands.push(text(42, 466, 13, 'Publication overview'), text(42, 448, 9, `${papers.length} publication${papers.length === 1 ? '' : 's'} included in this report`, '0.33 0.42 0.53'), line(42, 436, 570, 436));
    } else {
      commands.push(text(42, 700, 15, 'Publication record'), text(42, 679, 9, data.author, '0.33 0.42 0.53'), line(42, 665, 570, 665));
    }
    let y = pageIndex === 0 ? 408 : 635;
    papers.slice(pageIndex * 8, pageIndex * 8 + 8).forEach((paper, localIndex) => {
      const number = pageIndex * 8 + localIndex + 1;
      commands.push(rect(42, y - 58, 528, 66, '1 1 1'), text(55, y - 10, 8, `PAPER ${String(number).padStart(2, '0')}  |  ${paper.publishedYear || 'YEAR UNAVAILABLE'}`, '0.66 0.46 0.12'));
      wrap(paper.title, 78).slice(0, 2).forEach((titleLine, index) => commands.push(text(55, y - 29 - index * 13, 9, titleLine)));
      y -= 77;
    });
    commands.push(line(42, 42, 570, 42), text(42, 25, 8, `Generated ${new Date().toLocaleString()}  |  NmIndex`, '0.43 0.50 0.58'));
    return commands.join('\n');
  });
  const fontId = 3 + streams.length * 2;
  const pageIds = streams.map((_, index) => 3 + index * 2);
  const objects = ['<< /Type /Catalog /Pages 2 0 R >>', `<< /Type /Pages /Kids [${pageIds.map((id) => `${id} 0 R`).join(' ')}] /Count ${streams.length} >>`];
  streams.forEach((stream, index) => { const pageId = pageIds[index]; objects.push(`<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] /Resources << /Font << /F1 ${fontId} 0 R >> >> /Contents ${pageId + 1} 0 R >>`, `<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`); });
  objects.push('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>');
  let pdf = '%PDF-1.4\n';
  const offsets = [0];
  objects.forEach((object, index) => { offsets.push(pdf.length); pdf += `${index + 1} 0 obj\n${object}\nendobj\n`; });
  const xref = pdf.length;
  pdf += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  offsets.slice(1).forEach((offset) => { pdf += `${String(offset).padStart(10, '0')} 00000 n \n`; });
  pdf += `trailer << /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF`;
  const link = document.createElement('a');
  link.href = URL.createObjectURL(new Blob([pdf], { type: 'application/pdf' }));
  link.download = `${clean(data.author).replace(/\s+/g, '-') || 'author'}-summary.pdf`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}
