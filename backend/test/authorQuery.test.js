const test = require('node:test');
const assert = require('node:assert/strict');
const { parseAuthorQuery, AUTHOR_QUERY_MIN, AUTHOR_QUERY_MAX } = require('../services/authorQuery');

test('limits are 2 and 200', () => {
  assert.equal(AUTHOR_QUERY_MIN, 2);
  assert.equal(AUTHOR_QUERY_MAX, 200);
});

test('empty, whitespace-only and one-character queries are refused', () => {
  for (const raw of [undefined, '', '   ', '\t\n', 'a', '  a  ']) {
    assert.ok(parseAuthorQuery(raw).error, `refuses ${JSON.stringify(raw)}`);
  }
});

test('two characters is the minimum, after trimming', () => {
  assert.deepEqual(parseAuthorQuery('ab'), { value: 'ab' });
  assert.deepEqual(parseAuthorQuery('   Li   '), { value: 'Li' });
});

test('200 characters is the maximum', () => {
  assert.equal(parseAuthorQuery('a'.repeat(200)).value.length, 200);
  assert.match(parseAuthorQuery('a'.repeat(201)).error, /at most 200/);
  // Surrounding whitespace does not count against the limit.
  assert.equal(parseAuthorQuery(`  ${'a'.repeat(200)}  `).value.length, 200);
});

test('real international names pass unchanged', () => {
  for (const name of [
    'Jorge Martínez-Bauset', "Yi'ang Li", "O'Connor", 'J. R. R. Tolkien', 'Anne-Marie Smith-Jones',
    'Søren Kierkegaard', 'Zoë Ćirić', '王小明', 'Дмитрий Иванов', 'محمد علي', 'Nguyễn Văn An', 'X Æ',
  ]) {
    assert.deepEqual(parseAuthorQuery(name), { value: name }, name);
  }
});

test('decomposed Unicode is normalized to the composed form the database stores', () => {
  const decomposed = 'Martínez'; // i + combining acute accent
  assert.equal(parseAuthorQuery(decomposed).value, 'Martínez');
});

test('a repeated parameter (?q=a&q=b) is refused rather than crashing', () => {
  assert.ok(parseAuthorQuery(['ab', 'cd']).error);
});

test('a name is optional when the caller searches by id, but still capped', () => {
  assert.deepEqual(parseAuthorQuery('', { required: false }), { value: '' });
  assert.deepEqual(parseAuthorQuery('A', { required: false }), { value: 'A' });
  assert.ok(parseAuthorQuery('a'.repeat(201), { required: false }).error);
});
