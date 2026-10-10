const test = require('node:test');
const assert = require('node:assert/strict');
const rules = require('../services/libraryPapers');

const NOW = Date.parse('2026-10-10T12:00:00.000Z');
const paper = (n, extra = {}) => ({
  id: `W${100000 + n}`, title: `Paper ${n}`, publishedYear: 2020, authorId: 'A5050585435', authorName: 'Author', ...extra,
});

test('parsePaper requires a publication id and the author it was saved from', () => {
  assert.deepEqual(rules.parsePaper(paper(1)), {
    id: 'W100001', title: 'Paper 1', publishedYear: 2020, authorId: 'A5050585435', authorName: 'Author',
  });
  assert.equal(rules.parsePaper(paper(1, { id: 'not-a-work' })), null);
  assert.equal(rules.parsePaper(paper(1, { id: 'W1; drop' })), null);
  assert.equal(rules.parsePaper(paper(1, { authorId: '' })), null, 'no author: the details view could not load it');
  assert.equal(rules.parsePaper(paper(1, { authorId: 'bad' })), null);
  assert.equal(rules.parsePaper(null), null);
});

test('parsePaper tolerates incomplete metadata', () => {
  const parsed = rules.parsePaper({ id: 'W1', authorId: 'A1' });
  assert.equal(parsed.title, 'Untitled publication');
  assert.equal(parsed.publishedYear, null);
  assert.equal(parsed.authorName, '');
  assert.equal(rules.parsePaper({ id: 'W1', authorId: 'A1', publishedYear: 'abc' }).publishedYear, null);
});

test('a saved paper stores a reference, not the full publication record', () => {
  const full = { ...paper(1), abstract: 'Long abstract', authors: [{ id: 'A1' }], totalCitations: 99, fieldDetails: [] };
  const stored = rules.addSavedPaper([], rules.parsePaper(full), NOW).savedPapers[0];
  assert.deepEqual(Object.keys(stored).sort(), ['authorId', 'authorName', 'id', 'publishedYear', 'savedAt', 'title']);
});

test('saving adds to the top; the same paper is never stored twice', () => {
  const one = rules.addSavedPaper([], paper(1), NOW - 1000).savedPapers;
  const two = rules.addSavedPaper(one, paper(2), NOW);
  assert.equal(two.status, 'added');
  assert.deepEqual(two.savedPapers.map((p) => p.id), ['W100002', 'W100001']);
  const again = rules.addSavedPaper(two.savedPapers, paper(1), NOW + 1000);
  assert.equal(again.status, 'exists');
  assert.equal(again.savedPapers.length, 2);
});

test('the 201st saved paper is refused', () => {
  let list = [];
  for (let i = 0; i < 200; i += 1) list = rules.addSavedPaper(list, paper(i), NOW + i).savedPapers;
  assert.equal(list.length, 200);
  const refused = rules.addSavedPaper(list, paper(200), NOW + 500);
  assert.equal(refused.status, 'limit');
  assert.equal(refused.savedPapers.length, 200);
  assert.equal(rules.addSavedPaper(list, paper(7), NOW + 600).status, 'exists', 're-saving one already saved is fine');
});

test('existing saved papers are never deleted by the new rules', () => {
  // Saved by an older version: over the new limit, no savedAt, odd id, no author.
  const legacy = [
    ...Array.from({ length: 230 }, (_, i) => ({ ...paper(i), savedAt: new Date(NOW - i * 1000).toISOString() })),
    { id: 'legacy-id', title: 'Old format', savedAt: '' },
    { id: 'W999', title: 'No author', savedAt: '' },
  ];
  const kept = rules.normalizeSavedPapers(legacy);
  assert.equal(kept.length, 232, 'all kept');
  assert.deepEqual(kept.slice(-2).map((p) => p.id), ['legacy-id', 'W999'], 'undated entries sort last, in stored order');
  assert.equal(rules.addSavedPaper(legacy, paper(900), NOW).status, 'limit', 'but the list cannot grow');
});

test('duplicates already stored are collapsed to the newest', () => {
  const list = [
    { ...paper(1, { title: 'Old' }), savedAt: new Date(NOW - 5000).toISOString() },
    { ...paper(1, { title: 'New' }), savedAt: new Date(NOW).toISOString() },
  ];
  assert.deepEqual(rules.normalizeSavedPapers(list).map((p) => p.title), ['New']);
});

test('removing a paper drops it from every collection and keeps the collections', () => {
  const saved = [{ ...paper(1), savedAt: '' }, { ...paper(2), savedAt: '' }];
  const collections = [
    { id: 'c1', name: 'Reading', paperIds: ['W100001', 'W100002'] },
    { id: 'c2', name: 'Empty', paperIds: [] },
  ];
  const next = rules.removeSavedPaper(saved, collections, 'W100001');
  assert.deepEqual(next.savedPapers.map((p) => p.id), ['W100002']);
  assert.deepEqual(next.collections, [
    { id: 'c1', name: 'Reading', paperIds: ['W100002'] },
    { id: 'c2', name: 'Empty', paperIds: [] },
  ]);
});
