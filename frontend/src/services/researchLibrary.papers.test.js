import {
  MAX_SAVED_PAPERS,
  getLibrary,
  removeSavedPaper,
  savePaperToCollection,
  toggleSavedPaper,
} from './researchLibrary';

const USER = 'user-1';
const KEY = `scholarMetricsLibrary:${USER}`;
const paper = (n) => ({
  id: `W${100000 + n}`, title: `Paper ${n}`, publishedYear: 2021, authorId: 'A5050585435', authorName: 'Author',
});
const savedPaper = (n) => ({ ...paper(n), savedAt: new Date(Date.now() - n * 1000).toISOString() });

const seed = (library) => localStorage.setItem(KEY, JSON.stringify({
  savedAuthors: [], savedPapers: [], recentAuthors: [], collections: [], ...library,
}));
const reply = (status, body) => Promise.resolve({ ok: status < 400, status, json: async () => body });

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem('token', 'test-token');
  global.fetch = jest.fn();
});
afterEach(() => { delete global.fetch; });

test('saving into a collection posts a reference, then records the collection', async () => {
  seed({ collections: [{ id: 'c1', name: 'Thesis', paperIds: [] }] });
  fetch
    .mockReturnValueOnce(reply(201, { savedPapers: [savedPaper(1)] }))
    .mockReturnValueOnce(reply(200, {}));

  const result = await savePaperToCollection(USER, { ...paper(1), abstract: 'not stored', authors: [] }, 'c1');

  expect(result).toEqual({ ok: true });
  const [postUrl, post] = fetch.mock.calls[0];
  expect(postUrl).toMatch(/\/api\/library\/saved-papers$/);
  // A reference only -- never the abstract, authors or citation figures.
  expect(Object.keys(JSON.parse(post.body)).sort()).toEqual(['authorId', 'authorName', 'id', 'publishedYear', 'title']);
  await new Promise((resolve) => setTimeout(resolve, 0));
  const [, put] = fetch.mock.calls[1];
  expect(put.method).toBe('PUT');
  expect(JSON.parse(put.body)).toEqual({ collections: [{ id: 'c1', name: 'Thesis', paperIds: ['W100001'] }] });
  expect(getLibrary(USER).collections[0].paperIds).toEqual(['W100001']);
});

test('at 200 saved papers the 201st is refused without a request', async () => {
  seed({ savedPapers: Array.from({ length: MAX_SAVED_PAPERS }, (_, i) => savedPaper(i)) });
  const result = await savePaperToCollection(USER, paper(999), '');
  expect(result).toMatchObject({ ok: false, limitReached: true });
  expect(result.message).toMatch(/up to 200 publications/);
  expect(fetch).not.toHaveBeenCalled();
  expect(getLibrary(USER).savedPapers).toHaveLength(200);
});

test('a 409 from the server puts the library back, collection included', async () => {
  const collections = [{ id: 'c1', name: 'Thesis', paperIds: ['W100002'] }];
  seed({ savedPapers: [savedPaper(2)], collections });
  fetch.mockReturnValueOnce(reply(409, { message: 'You can save up to 200 publications.', savedPapers: [savedPaper(2)] }));

  const result = await savePaperToCollection(USER, paper(1), 'c1');

  expect(result).toMatchObject({ ok: false, limitReached: true });
  expect(getLibrary(USER).savedPapers.map((p) => p.id)).toEqual(['W100002']);
  expect(getLibrary(USER).collections).toEqual(collections);
  expect(fetch).toHaveBeenCalledTimes(1);
});

test('moving an already-saved paper to another collection does not re-save it', async () => {
  seed({
    savedPapers: [savedPaper(1)],
    collections: [{ id: 'c1', name: 'A', paperIds: ['W100001'] }, { id: 'c2', name: 'B', paperIds: [] }],
  });
  fetch.mockReturnValueOnce(reply(200, {}));
  await savePaperToCollection(USER, paper(1), 'c2');
  // The collection PUT goes through the existing write queue, a tick later.
  await new Promise((resolve) => setTimeout(resolve, 0));
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(fetch.mock.calls[0][1].method).toBe('PUT');
  expect(getLibrary(USER).collections.map((c) => c.paperIds)).toEqual([[], ['W100001']]);
});

test('removing a paper takes it out of its collection; the collection stays', async () => {
  seed({ savedPapers: [savedPaper(1), savedPaper(2)], collections: [{ id: 'c1', name: 'Thesis', paperIds: ['W100001', 'W100002'] }] });
  fetch.mockReturnValueOnce(reply(200, { savedPapers: [savedPaper(2)] }));

  expect((await removeSavedPaper(USER, 'W100001')).ok).toBe(true);

  expect(fetch.mock.calls[0][0]).toMatch(/\/saved-papers\/W100001$/);
  expect(fetch.mock.calls[0][1].method).toBe('DELETE');
  expect(getLibrary(USER).savedPapers.map((p) => p.id)).toEqual(['W100002']);
  expect(getLibrary(USER).collections).toEqual([{ id: 'c1', name: 'Thesis', paperIds: ['W100002'] }]);
});

test('a failed removal restores the paper and its collection', async () => {
  const before = { savedPapers: [savedPaper(1)], collections: [{ id: 'c1', name: 'Thesis', paperIds: ['W100001'] }] };
  seed(before);
  fetch.mockRejectedValueOnce(new TypeError('Failed to fetch'));
  const result = await removeSavedPaper(USER, 'W100001');
  expect(result.ok).toBe(false);
  expect(result.message).toMatch(/connection/i);
  expect(getLibrary(USER).savedPapers.map((p) => p.id)).toEqual(['W100001']);
  expect(getLibrary(USER).collections).toEqual(before.collections);
});

test('toggle on a saved paper removes it (the Data Explorer "Saved" button)', async () => {
  seed({ savedPapers: [savedPaper(1)] });
  fetch.mockReturnValueOnce(reply(200, { savedPapers: [] }));
  expect((await toggleSavedPaper(USER, paper(1))).ok).toBe(true);
  expect(getLibrary(USER).savedPapers).toEqual([]);
});
