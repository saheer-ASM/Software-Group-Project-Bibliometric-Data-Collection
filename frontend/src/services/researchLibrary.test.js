import {
  MAX_SAVED_AUTHORS,
  clearRecentAuthors,
  getLibrary,
  recordRecentAuthor,
  removeRecentAuthor,
  removeSavedAuthor,
  saveAuthor,
  syncLibraryFromServer,
  toggleSavedAuthor,
} from './researchLibrary';

const USER = 'user-1';
const KEY = `scholarMetricsLibrary:${USER}`;
const DAY = 24 * 60 * 60 * 1000;
const author = (n) => ({ id: `A${1000 + n}`, name: `Author ${n}` });
const ago = (ms) => new Date(Date.now() - ms).toISOString();

const seed = (library) => localStorage.setItem(KEY, JSON.stringify({
  savedAuthors: [], savedPapers: [], recentAuthors: [], collections: [], ...library,
}));

const reply = (status, body) => Promise.resolve({ ok: status < 400, status, json: async () => body });

beforeEach(() => {
  localStorage.clear();
  global.fetch = jest.fn();
});
afterEach(() => { delete global.fetch; });

describe('signed in', () => {
  beforeEach(() => localStorage.setItem('token', 'test-token'));

  test('saving posts one author and adopts the server list', async () => {
    const server = [{ ...author(1), savedAt: ago(0) }];
    fetch.mockReturnValueOnce(reply(201, { savedAuthors: server }));

    const result = await saveAuthor(USER, author(1));

    expect(result).toEqual({ ok: true, saved: true });
    const [url, init] = fetch.mock.calls[0];
    expect(url).toMatch(/\/api\/library\/saved-authors$/);
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body)).toEqual({ id: 'A1001', name: 'Author 1' });
    expect(init.headers.Authorization).toBe('Bearer test-token');
    expect(getLibrary(USER).savedAuthors).toEqual(server);
  });

  test('a 409 from the server undoes the optimistic save and explains why', async () => {
    const full = Array.from({ length: 100 }, (_, i) => ({ ...author(i), savedAt: ago(i) }));
    seed({ savedAuthors: full.slice(0, 99) });
    fetch.mockReturnValueOnce(reply(409, { message: 'You can save up to 100 authors.', savedAuthors: full }));

    const result = await saveAuthor(USER, author(500));

    expect(result.ok).toBe(false);
    expect(result.limitReached).toBe(true);
    expect(result.message).toMatch(/up to 100/);
    expect(getLibrary(USER).savedAuthors.map((a) => a.id)).not.toContain('A1500');
    expect(getLibrary(USER).savedAuthors).toHaveLength(100);
  });

  test('a network failure undoes the save', async () => {
    fetch.mockRejectedValueOnce(new TypeError('Failed to fetch'));
    const result = await saveAuthor(USER, author(1));
    expect(result.ok).toBe(false);
    expect(result.message).toMatch(/connection/i);
    expect(getLibrary(USER).savedAuthors).toEqual([]);
  });

  test('at 100 saved, the 101st is refused without a request', async () => {
    seed({ savedAuthors: Array.from({ length: MAX_SAVED_AUTHORS }, (_, i) => ({ ...author(i), savedAt: ago(i) })) });
    const result = await saveAuthor(USER, author(999));
    expect(result).toMatchObject({ ok: false, limitReached: true });
    expect(fetch).not.toHaveBeenCalled();
  });

  test('saving an author already saved sends nothing', async () => {
    seed({ savedAuthors: [{ ...author(1), savedAt: ago(0) }] });
    expect(await saveAuthor(USER, author(1))).toEqual({ ok: true, saved: true });
    expect(fetch).not.toHaveBeenCalled();
  });

  test('a failed removal puts the author back in place', async () => {
    seed({ savedAuthors: [{ ...author(1), savedAt: ago(0) }, { ...author(2), savedAt: ago(DAY) }] });
    fetch.mockReturnValueOnce(reply(500, { message: 'Unable to remove this author.' }));

    const result = await removeSavedAuthor(USER, 'A1001');

    expect(result).toMatchObject({ ok: false, saved: true });
    expect(getLibrary(USER).savedAuthors.map((a) => a.id)).toEqual(['A1001', 'A1002']);
  });

  test('toggle removes a saved author through DELETE', async () => {
    seed({ savedAuthors: [{ ...author(1), savedAt: ago(0) }] });
    fetch.mockReturnValueOnce(reply(200, { savedAuthors: [] }));

    const result = await toggleSavedAuthor(USER, author(1));

    expect(result).toEqual({ ok: true, saved: false });
    expect(fetch.mock.calls[0][0]).toMatch(/\/saved-authors\/A1001$/);
    expect(fetch.mock.calls[0][1].method).toBe('DELETE');
  });

  test('viewing an author records it and adopts the server history', async () => {
    const server = [{ ...author(1), viewedAt: ago(0) }];
    fetch.mockReturnValueOnce(reply(200, { recentAuthors: server }));
    await recordRecentAuthor(USER, author(1));
    expect(fetch.mock.calls[0][0]).toMatch(/\/recent-authors$/);
    expect(getLibrary(USER).recentAuthors).toEqual(server);
  });

  test('a failed history request is silent and keeps the local view', async () => {
    fetch.mockRejectedValueOnce(new TypeError('Failed to fetch'));
    await expect(recordRecentAuthor(USER, author(1))).resolves.toBeUndefined();
    expect(getLibrary(USER).recentAuthors.map((a) => a.id)).toEqual(['A1001']);
  });

  test('clearing history; a failure restores it', async () => {
    seed({ recentAuthors: [{ ...author(1), viewedAt: ago(0) }] });
    fetch.mockReturnValueOnce(reply(500, { message: 'Unable to clear your history.' }));
    expect((await clearRecentAuthors(USER)).ok).toBe(false);
    expect(getLibrary(USER).recentAuthors).toHaveLength(1);

    fetch.mockReturnValueOnce(reply(200, { recentAuthors: [] }));
    expect((await clearRecentAuthors(USER)).ok).toBe(true);
    expect(getLibrary(USER).recentAuthors).toEqual([]);
  });

  test('removing one history entry', async () => {
    seed({ recentAuthors: [{ ...author(1), viewedAt: ago(0) }, { ...author(2), viewedAt: ago(1000) }] });
    fetch.mockReturnValueOnce(reply(200, { recentAuthors: [{ ...author(2), viewedAt: ago(1000) }] }));
    expect((await removeRecentAuthor(USER, 'A1001')).ok).toBe(true);
    expect(getLibrary(USER).recentAuthors.map((a) => a.id)).toEqual(['A1002']);
  });

  test('sync: the server list wins for authors, so a removal elsewhere stays removed', async () => {
    // This browser still holds A1002, which another device removed.
    seed({
      savedAuthors: [{ ...author(1), savedAt: ago(DAY) }, { ...author(2), savedAt: ago(2 * DAY) }],
      savedPapers: [{ id: 'W-local', title: 'Local paper' }],
    });
    fetch
      .mockReturnValueOnce(reply(200, {
        savedAuthors: [{ ...author(1), savedAt: ago(DAY) }],
        recentAuthors: [],
        savedPapers: [{ id: 'W-remote', title: 'Remote paper' }],
        collections: [],
      }))
      .mockReturnValueOnce(reply(200, {}));

    const merged = await syncLibraryFromServer(USER);

    expect(merged.savedAuthors.map((a) => a.id)).toEqual(['A1001']);
    // Saved papers follow the server too now, so a paper removed elsewhere stays removed.
    expect(merged.savedPapers.map((p) => p.id)).toEqual(['W-remote']);
    // The follow-up PUT carries collections only.
    const putBody = JSON.parse(fetch.mock.calls[1][1].body);
    expect(Object.keys(putBody)).toEqual(['collections']);
  });
});

describe('guest (no token): local only, same rules', () => {
  test('no requests are made', async () => {
    await saveAuthor(USER, author(1));
    await recordRecentAuthor(USER, author(1));
    expect(fetch).not.toHaveBeenCalled();
    expect(getLibrary(USER).savedAuthors).toHaveLength(1);
  });

  test('history keeps 100 unique authors, newest first', async () => {
    for (let i = 0; i < 105; i += 1) {
      // eslint-disable-next-line no-await-in-loop
      await recordRecentAuthor(USER, author(i));
    }
    await recordRecentAuthor(USER, author(50)); // a revisit moves it to the top
    const history = getLibrary(USER).recentAuthors;
    expect(history).toHaveLength(100);
    expect(new Set(history.map((a) => a.id)).size).toBe(100);
    expect(history[0].id).toBe('A1050');
  });

  test('entries older than 30 days are not shown', () => {
    seed({
      recentAuthors: [
        { ...author(1), viewedAt: ago(DAY) },
        { ...author(2), viewedAt: ago(31 * DAY) },
      ],
    });
    expect(getLibrary(USER).recentAuthors.map((a) => a.id)).toEqual(['A1001']);
  });
});
