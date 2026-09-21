import { filterPublications, impactLevel, publicationYears } from './publicationFilters';

const papers = [
  { id: 'a', title: 'Computer networks', fields: ['Computer Science'], publishedYear: 2022, totalCitations: 10, adjustedCitations: 7, selfCitations: 2, authorContributionWeight: 0.25, authors: [{ id: 'me', position: 1, weight: 0.25 }] },
  { id: 'b', title: 'Computer vision', fields: ['Computer Science'], publishedYear: 2025, totalCitations: 5, adjustedCitations: 0, selfCitations: 5, authorContributionWeight: 10, authors: [{ id: 'me', position: 2, weight: 10 }] },
  { id: 'c', title: 'Biology', fields: ['Biology'], publishedYear: 2020, totalCitations: 1, adjustedCitations: 0.5, selfCitations: 0, authors: [] },
  { id: 'd', title: 'Unknown year', fields: [], publishedYear: null, totalCitations: 0, adjustedCitations: 0, selfCitations: 0, authors: [] },
];
const ids = filters => filterPublications(papers, filters, 'me').map(p => p.id);

test('combines field, inclusive year range, title, contribution, impact and citation type', () => {
  expect(ids({ field: 'Computer Science', years: [2022, 2025], citationType: 'adjusted', query: 'NETWORK', contribution: 'major', impact: 'medium', view: 'adjusted' })).toEqual(['a']);
  expect(ids({ years: [2022, 2025] })).toEqual(['a', 'b']);
  expect(ids({})).toEqual(['a', 'b', 'c', 'd']);
  expect(ids({ field: 'Biology', years: [2022, 2025] })).toEqual([]);
});

test.each([[0, 'uncited'], [0.5, 'low'], [4, 'low'], [5, 'medium'], [9.999, 'medium'], [10, 'high']])('classifies %s citations', (value, expected) => {
  expect(impactLevel(value)).toBe(expected);
});

test('uses existing normal, self and adjusted values without changing data', () => {
  const snapshot = JSON.stringify(papers);
  expect(ids({ citationType: 'self' })).toEqual(['a', 'b']);
  expect(ids({ citationType: 'external' })).toEqual(['a', 'c']);
  expect(ids({ citationType: 'adjusted' })).toEqual(['a', 'c']);
  expect(ids({ impact: 'high' })).toEqual(['a']);
  expect(ids({ impact: 'high', view: 'adjusted' })).toEqual([]);
  expect(ids({ impact: 'low', view: 'adjusted' })).toEqual(['c']);
  expect(ids({ impact: 'uncited' })).toEqual(['d']);
  expect(ids({ impact: 'uncited', view: 'adjusted' })).toEqual(['b', 'd']);
  expect(JSON.stringify(papers)).toBe(snapshot);
});

test('supports author roles, both weight formats and missing contribution weights', () => {
  expect(ids({ contribution: 'primary' })).toEqual(['a']);
  expect(ids({ contribution: 'major' })).toEqual(['a']);
  expect(ids({ contribution: 'minor' })).toEqual(['b']);
  expect(ids({ contribution: 'coauthor' })).toEqual(['b']);
  expect(ids({ contribution: '' })).toEqual(['a', 'b', 'c', 'd']);
  expect(filterPublications([{ ...papers[0], authorContributionWeight: 25 }], { contribution: 'major' }, 'me')).toHaveLength(1);
});

test('derives year bounds and handles empty, unknown and single-year data', () => {
  expect(publicationYears(papers)).toEqual([2020, 2022, 2025]);
  expect(publicationYears([])).toEqual([]);
  expect(publicationYears([{ publishedYear: null }, { publishedYear: 'unknown' }])).toEqual([]);
  expect(publicationYears([{ publishedYear: '2022' }, { publishedYear: 2022 }])).toEqual([2022]);
});
