import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import DataExplorer from './DataExplorer';

jest.mock('recharts', () => ({
  ResponsiveContainer: ({ children }) => children,
  LineChart: () => null, Line: () => null, XAxis: () => null, YAxis: () => null,
  CartesianGrid: () => null, Tooltip: () => null, Legend: () => null,
}));

const paper = (id, year, field, adjusted) => ({
  id, title: `Publication ${id}`, publishedYear: year, fields: [field], fieldDetails: [],
  authors: [{ id: 'researcher', name: 'Researcher', position: 1, weight: 0.5 }],
  authorContributionWeight: 0.5, totalCitations: 12, selfCitations: 2,
  adjustedCitations: adjusted, averageIsc: 0.2,
});

const PAPERS = [
  paper('A', 2022, 'Computer Science', 7),
  paper('B', 2025, 'Computer Science', 0),
  paper('C', 2020, 'Biology', 5),
];

const profile = {
  authorId: 'researcher', author: 'Researcher', totalPublications: 3,
  totalCitations: 36, totalSelfCitations: 6, totalAdjustedCitations: 12,
  nmIndex: 77.123, hIndex: 3, cScore: 88.456, careerCompensation: 1,
  trendData: [], publications: PAPERS,
  publicationsPagination: {
    page: 1, limit: 20, total: 3, totalPages: 1, hasNextPage: false, hasPreviousPage: false,
  },
  publicationFacets: { years: [2020, 2022, 2025], fields: ['Biology', 'Computer Science'] },
};

// Filtering runs in SQL, so the component answers a filter change by asking the
// server for page 1 of the filtered set. The stub returns the current `filtered`
// value and records the query it was asked for.
let filtered;
let requests;

const mockFetch = () => jest.fn((url) => {
  const href = String(url);
  if (href.includes('/api/search/publications')) {
    requests.push(new URL(href, 'http://localhost').searchParams);
    return Promise.resolve({
      ok: true,
      json: async () => ({
        publications: filtered,
        pagination: {
          page: 1, limit: 20, total: filtered.length,
          totalPages: Math.max(1, Math.ceil(filtered.length / 20)),
          hasNextPage: false, hasPreviousPage: false,
        },
      }),
    });
  }
  return Promise.resolve({ ok: true, json: async () => profile });
});

beforeEach(() => {
  filtered = PAPERS;
  requests = [];
  global.fetch = mockFetch();
});

afterEach(() => { delete global.fetch; localStorage.clear(); });

const lastRequest = () => requests[requests.length - 1];

const renderExplorer = () => render(
  <MemoryRouter initialEntries={['/data-explorer']}>
    <DataExplorer authorName="Researcher" />
  </MemoryRouter>,
);

test('loads the profile and renders page 1 with the server facets', async () => {
  renderExplorer();
  await screen.findByRole('heading', { name: 'Publication A' });

  expect(screen.getByRole('heading', { name: 'Publication B' })).toBeInTheDocument();
  // Year bounds come from publicationFacets, not from the loaded rows.
  expect(screen.getByRole('slider', { name: /Start Year/ })).toHaveAttribute('min', '2020');
  expect(screen.getByText('Showing', { exact: false }).textContent).toBe('Showing 3 of 3 publications');
  // No publications request yet: page 1 arrived with the author payload.
  expect(requests).toHaveLength(0);
});

test('combined filters are sent to the server and the list is replaced by its answer', async () => {
  renderExplorer();
  await screen.findByRole('heading', { name: 'Publication A' });

  filtered = [PAPERS[0]];
  fireEvent.change(screen.getByLabelText('FIELD'), { target: { value: 'Computer Science' } });
  fireEvent.change(screen.getByRole('slider', { name: /Start Year/ }), { target: { value: '2022' } });
  fireEvent.change(screen.getByLabelText('CITATION TYPE'), { target: { value: 'adjusted' } });

  await waitFor(() => expect(screen.queryByRole('heading', { name: 'Publication B' })).not.toBeInTheDocument());
  expect(screen.queryByRole('heading', { name: 'Publication C' })).not.toBeInTheDocument();
  expect(screen.getByRole('heading', { name: 'Publication A' })).toBeInTheDocument();

  // Every active filter travels as a query parameter, and paging restarts at 1.
  const sent = lastRequest();
  expect(sent.get('field')).toBe('Computer Science');
  expect(sent.get('yearFrom')).toBe('2022');
  expect(sent.get('citationType')).toBe('adjusted');
  expect(sent.get('page')).toBe('1');
  expect(sent.get('authorId')).toBe('researcher');

  // The filtered total drives the count, not the number of loaded rows.
  expect(screen.getByText('Showing', { exact: false }).textContent).toBe('Showing 1 of 1 publications');
  expect(screen.getByText('Adjusted citations')).toBeInTheDocument();
  expect(screen.queryByRole('group', { name: 'Citation View' })).not.toBeInTheDocument();
});

test('an empty filtered result shows the empty state and leaves metrics untouched', async () => {
  renderExplorer();
  await screen.findByRole('heading', { name: 'Publication A' });

  filtered = [];
  fireEvent.change(screen.getByLabelText('PUBLICATION IMPACT'), { target: { value: 'low' } });

  await waitFor(() => expect(screen.getByText('No publications match these filters')).toBeInTheDocument());
  expect(lastRequest().get('impact')).toBe('low');
  // Author-level metrics are computed over the whole corpus and must not move.
  expect(screen.getByText('77.123')).toBeInTheDocument();
  expect(screen.getByText('88.456')).toBeInTheDocument();
});

test('clearing the filters restores the full list and the default controls', async () => {
  renderExplorer();
  await screen.findByRole('heading', { name: 'Publication A' });

  filtered = [];
  fireEvent.change(screen.getByLabelText('PUBLICATION IMPACT'), { target: { value: 'low' } });
  await waitFor(() => expect(screen.getByText('No publications match these filters')).toBeInTheDocument());

  filtered = PAPERS;
  fireEvent.click(screen.getAllByRole('button', { name: 'Clear filters' })[0]);

  await waitFor(() => expect(screen.getAllByRole('heading', { name: /^Publication [ABC]$/ })).toHaveLength(3));
  expect(screen.getByLabelText('All years')).toBeChecked();
  expect(screen.queryByRole('radio')).not.toBeInTheDocument();
  expect(screen.getAllByRole('combobox').filter((el) => el.tagName === 'SELECT')).toHaveLength(4);
  expect(screen.queryByRole('option', { name: 'Calculated' })).not.toBeInTheDocument();
  expect(screen.queryByRole('option', { name: 'Not calculated' })).not.toBeInTheDocument();
  expect(screen.queryByLabelText('Citation Impact')).not.toBeInTheDocument();
  expect(screen.queryByLabelText('Impact Level')).not.toBeInTheDocument();
});
