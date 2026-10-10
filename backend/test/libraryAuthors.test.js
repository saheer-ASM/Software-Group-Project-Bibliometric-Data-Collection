const test = require('node:test');
const assert = require('node:assert/strict');
const rules = require('../services/libraryAuthors');

const DAY = 24 * 60 * 60 * 1000;
const NOW = Date.parse('2026-10-10T12:00:00.000Z');
const at = (msAgo) => new Date(NOW - msAgo).toISOString();
const author = (n) => ({ id: `A${1000 + n}`, name: `Author ${n}` });

test('parseAuthor accepts OpenAlex ids only', () => {
  assert.deepEqual(rules.parseAuthor({ id: 'A5050585435', name: ' Ada ' }), { id: 'A5050585435', name: 'Ada' });
  assert.deepEqual(rules.parseAuthor({ id: 'A1' }), { id: 'A1', name: 'A1' });
  for (const id of ['', 'a123', 'A', 'A12x', '../A1', 'A1 OR 1=1', 123, null]) {
    assert.equal(rules.parseAuthor({ id, name: 'x' }), null, `rejects ${JSON.stringify(id)}`);
  }
  assert.equal(rules.parseAuthor(null), null);
});

test('saving adds to the top, newest first', () => {
  const first = rules.addSavedAuthor([], author(1), NOW - 1000);
  const second = rules.addSavedAuthor(first.savedAuthors, author(2), NOW);
  assert.equal(second.status, 'added');
  assert.deepEqual(second.savedAuthors.map((a) => a.id), ['A1002', 'A1001']);
});

test('saving the same author twice never duplicates it', () => {
  const once = rules.addSavedAuthor([], author(1), NOW).savedAuthors;
  const twice = rules.addSavedAuthor(once, author(1), NOW + 5000);
  assert.equal(twice.status, 'exists');
  assert.equal(twice.savedAuthors.length, 1);
  // The original savedAt is kept: re-saving is a no-op, not a bump.
  assert.equal(twice.savedAuthors[0].savedAt, once[0].savedAt);
});

test('the 101st saved author is refused', () => {
  let list = [];
  for (let i = 0; i < 100; i += 1) list = rules.addSavedAuthor(list, author(i), NOW + i).savedAuthors;
  assert.equal(list.length, 100);
  const refused = rules.addSavedAuthor(list, author(100), NOW + 200);
  assert.equal(refused.status, 'limit');
  assert.equal(refused.savedAuthors.length, 100);
  // ...but re-saving one already in the list is still fine at the limit.
  assert.equal(rules.addSavedAuthor(list, author(5), NOW + 300).status, 'exists');
});

test('a list already over the old 500 cap is shown in full, never truncated', () => {
  const legacy = Array.from({ length: 120 }, (_, i) => ({ ...author(i), savedAt: at(i * 1000) }));
  assert.equal(rules.normalizeSaved(legacy).length, 120);
  assert.equal(rules.addSavedAuthor(legacy, author(500), NOW).status, 'limit');
  // Removing still works, so the user can get back under the limit.
  assert.equal(rules.removeSavedAuthor(legacy, 'A1000').length, 119);
});

test('legacy duplicates and junk are cleaned, newest stamp wins', () => {
  const messy = [
    { id: 'A1', name: 'Old', savedAt: at(5 * DAY) },
    { id: 'A1', name: 'New', savedAt: at(1 * DAY) },
    { id: 'bad', name: 'x', savedAt: at(0) },
    { id: 'A2', name: 'No date' },
    { id: 'A3', name: 'Ok', savedAt: at(2 * DAY) },
  ];
  assert.deepEqual(rules.normalizeSaved(messy).map((a) => `${a.id}:${a.name}`), ['A1:New', 'A3:Ok']);
});

test('removing a saved author', () => {
  const list = [{ ...author(1), savedAt: at(0) }, { ...author(2), savedAt: at(1) }];
  assert.deepEqual(rules.removeSavedAuthor(list, 'A1001').map((a) => a.id), ['A1002']);
  assert.equal(rules.removeSavedAuthor(list, 'A9999').length, 2, 'removing a missing id is harmless');
});

test('a revisit moves the author to the top without a duplicate', () => {
  let list = [];
  list = rules.recordRecentAuthor(list, author(1), NOW - 3000);
  list = rules.recordRecentAuthor(list, author(2), NOW - 2000);
  list = rules.recordRecentAuthor(list, { id: 'A1001', name: 'Renamed' }, NOW);
  assert.deepEqual(list.map((a) => a.id), ['A1001', 'A1002']);
  assert.equal(list[0].name, 'Renamed');
  assert.equal(list[0].viewedAt, new Date(NOW).toISOString());
});

test('history keeps at most 100 unique authors, dropping the oldest', () => {
  let list = [];
  for (let i = 0; i < 130; i += 1) list = rules.recordRecentAuthor(list, author(i), NOW - (130 - i) * 1000);
  assert.equal(list.length, 100);
  assert.equal(list[0].id, 'A1129', 'newest first');
  assert.equal(list[99].id, 'A1030', 'the 30 oldest were dropped');
});

test('views older than 30 days are excluded and pruned', () => {
  const list = [
    { ...author(1), viewedAt: at(1 * DAY) },
    { ...author(2), viewedAt: at(30 * DAY - 1000) },
    { ...author(3), viewedAt: at(30 * DAY + 1000) },
    { ...author(4), viewedAt: at(90 * DAY) },
  ];
  assert.deepEqual(rules.normalizeRecent(list, NOW).map((a) => a.id), ['A1001', 'A1002']);
  // Recording a new view also drops expired entries from what is stored.
  const stored = rules.recordRecentAuthor(list, author(9), NOW);
  assert.deepEqual(stored.map((a) => a.id), ['A1009', 'A1001', 'A1002']);
});

test('removing one history entry', () => {
  const list = [{ ...author(1), viewedAt: at(0) }, { ...author(2), viewedAt: at(1000) }];
  assert.deepEqual(rules.removeRecentAuthor(list, 'A1001', NOW).map((a) => a.id), ['A1002']);
});
