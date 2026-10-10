/* Mobile "Show Details" collapse on the publication cards. Renders the real
   DataExplorer with a stubbed API so the toggle is exercised through the same
   state the app uses, rather than against a copy of the markup. */
import React from 'react';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import DataExplorer from './DataExplorer';
import { AppShellContext } from './appShell';

// Recharts' ResponsiveContainer needs ResizeObserver, which jsdom lacks.
global.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
};

const publication = (id, title, year, citations) => ({
  id,
  title,
  abstract: `Abstract for ${title}`,
  source: 'Test Journal',
  fields: ['Computer Networks and Communications'],
  fieldDetails: [
    { name: 'Computer Networks and Communications', weight: 0.901 },
    { name: 'Electrical and Electronic Engineering', weight: 0.042 },
  ],
  authors: [
    { id: 'A1', name: 'Patikiri Arachchige Don Shehan Nilmantha Wijesekara', weight: 0.6666, position: 1 },
    { id: 'A2', name: 'Subodha Gunawardena', weight: 0.3333, position: 2 },
  ],
  authorContributionWeight: 0.6666,
  authorOrdering: 'Alphabetical',
  selfCitations: 6,
  averageIsc: 0.802,
  publishedYear: year,
  totalCitations: citations,
  rawCitations: citations,
  adjustedCitations: 11.461,
  citingPaperCount: citations,
});

const authorPayload = (publications, total) => ({
  authorId: 'A5050585435',
  author: 'Test Author',
  totalPublications: total,
  totalCitations: 100,
  totalSelfCitations: 10,
  totalAdjustedCitations: 50,
  nmIndex: 99.947,
  hIndex: 8,
  cScore: 165.12,
  careerCompensation: 1.112,
  publications,
  publicationsPagination: {
    page: 1,
    limit: 20,
    total,
    totalPages: Math.ceil(total / 20),
    hasNextPage: total > publications.length,
    hasPreviousPage: false,
  },
  publicationFacets: { years: [2023, 2024], fields: ['Computer Networks and Communications'] },
  trendData: [],
  annualCitationImpact: [],
  scoreDetails: null,
});

const PAGE_1 = [
  publication('P1', 'First publication about routing', 2023, 22),
  publication('P2', 'Second publication about learning', 2024, 11),
];
const PAGE_2 = [publication('P3', 'Third publication from page two', 2022, 5)];

const publicationsResponse = (rows, page, total, hasNextPage) => ({
  ok: true,
  json: () => Promise.resolve({
    publications: rows,
    pagination: {
      page, limit: 20, total, totalPages: Math.ceil(total / 20), hasNextPage, hasPreviousPage: page > 1,
    },
  }),
});

let fetchMock;

beforeEach(() => {
  window.localStorage.clear();
  fetchMock = jest.fn((url) => {
    if (String(url).includes('/api/search/publications')) {
      const page = Number(new URL(String(url), 'http://localhost').searchParams.get('page')) || 1;
      return Promise.resolve(page === 2
        ? publicationsResponse(PAGE_2, 2, 3, false)
        : publicationsResponse(PAGE_1, 1, 3, true));
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve(authorPayload(PAGE_1, 3)) });
  });
  global.fetch = fetchMock;
});

// DataExplorer renders the shared navbar/footer, which need the router and the
// app-shell context that App.js normally supplies.
const shell = { isAdmin: false, goTo: jest.fn(), openSupport: jest.fn() };

const renderExplorer = () => render(
  <MemoryRouter initialEntries={['/explorer']}>
    <AppShellContext.Provider value={shell}>
      <DataExplorer authorName="Test Author" user={{ uid: 'u1' }} />
    </AppShellContext.Provider>
  </MemoryRouter>,
);

const card = (title) => screen.getByText(title).closest('.de-pub-card');
const toggleIn = (title) => within(card(title)).getByRole('button', { name: /details/i });

async function loaded() {
  await waitFor(
    () => expect(screen.getByText('First publication about routing')).toBeInTheDocument(),
    { timeout: 5000 },
  );
}

test('every card starts collapsed, with one real button per card', async () => {
  renderExplorer();
  await loaded();

  const toggles = screen.getAllByRole('button', { name: /show details/i });
  expect(toggles).toHaveLength(2);
  toggles.forEach((button) => {
    expect(button).toHaveAttribute('aria-expanded', 'false');
    expect(button.tagName).toBe('BUTTON');
  });
  expect(document.querySelectorAll('.de-pub-card-expanded')).toHaveLength(0);
});

test('the toggle is wired to the metrics and the fields/authors blocks', async () => {
  renderExplorer();
  await loaded();

  const button = toggleIn('First publication about routing');
  const controlled = button.getAttribute('aria-controls').split(' ');
  expect(controlled).toHaveLength(2);
  expect(document.getElementById(controlled[0])).toHaveClass('de-pub-stats');
  expect(document.getElementById(controlled[1])).toHaveClass('de-pub-secondary');
});

test('expanding one card leaves the other collapsed', async () => {
  renderExplorer();
  await loaded();

  await userEvent.click(toggleIn('First publication about routing'));

  expect(toggleIn('First publication about routing')).toHaveAttribute('aria-expanded', 'true');
  expect(toggleIn('First publication about routing')).toHaveTextContent('Hide Details');
  expect(toggleIn('Second publication about learning')).toHaveAttribute('aria-expanded', 'false');
  expect(toggleIn('Second publication about learning')).toHaveTextContent('Show Details');

  expect(card('First publication about routing')).toHaveClass('de-pub-card-expanded');
  expect(card('Second publication about learning')).not.toHaveClass('de-pub-card-expanded');
});

test('Hide Details collapses that card again', async () => {
  renderExplorer();
  await loaded();

  await userEvent.click(toggleIn('First publication about routing'));
  expect(card('First publication about routing')).toHaveClass('de-pub-card-expanded');

  await userEvent.click(toggleIn('First publication about routing'));
  expect(card('First publication about routing')).not.toHaveClass('de-pub-card-expanded');
  expect(toggleIn('First publication about routing')).toHaveTextContent('Show Details');
});

test('toggling fires no network request', async () => {
  renderExplorer();
  await loaded();

  const before = fetchMock.mock.calls.length;
  await userEvent.click(toggleIn('First publication about routing'));
  await userEvent.click(toggleIn('Second publication about learning'));
  await userEvent.click(toggleIn('First publication about routing'));
  expect(fetchMock.mock.calls.length).toBe(before);
});

test('collapsed content stays in the DOM and is never duplicated', async () => {
  renderExplorer();
  await loaded();

  expect(document.querySelectorAll('.de-pub-stats')).toHaveLength(2);
  expect(document.querySelectorAll('.de-pub-secondary')).toHaveLength(2);

  const firstCard = card('First publication about routing');
  expect(within(firstCard).getAllByText('Self citations')).toHaveLength(1);
  expect(within(firstCard).getAllByText('Research fields')).toHaveLength(1);
  expect(within(firstCard).getAllByText('Author contributions')).toHaveLength(1);
  expect(within(firstCard).getAllByText(/Subodha Gunawardena/)).toHaveLength(1);
});

test('Read abstract still works alongside the new toggle', async () => {
  renderExplorer();
  await loaded();

  const firstCard = card('First publication about routing');
  expect(within(firstCard).getByText('Read abstract')).toBeInTheDocument();
  expect(within(firstCard).getByText('Abstract for First publication about routing')).toBeInTheDocument();
});

test('Load More keeps expanded state and adds no duplicate cards', async () => {
  renderExplorer();
  await loaded();

  await userEvent.click(toggleIn('First publication about routing'));
  await userEvent.click(screen.getByRole('button', { name: /load more/i }));

  await waitFor(() => expect(screen.getByText('Third publication from page two')).toBeInTheDocument());

  expect(document.querySelectorAll('.de-pub-card')).toHaveLength(3);
  expect(card('First publication about routing')).toHaveClass('de-pub-card-expanded');
  expect(card('Third publication from page two')).not.toHaveClass('de-pub-card-expanded');
  expect(toggleIn('Third publication from page two')).toHaveAttribute('aria-expanded', 'false');
});

test('a filter change drops expanded state for publications that left the list', async () => {
  renderExplorer();
  await loaded();

  await userEvent.click(toggleIn('First publication about routing'));
  expect(document.querySelectorAll('.de-pub-card-expanded')).toHaveLength(1);

  fetchMock.mockImplementation((url) => {
    if (String(url).includes('/api/search/publications')) {
      return Promise.resolve(publicationsResponse(PAGE_2, 1, 1, false));
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve(authorPayload(PAGE_1, 3)) });
  });

  await userEvent.selectOptions(screen.getByLabelText(/publication impact/i), 'high');

  await waitFor(
    () => expect(screen.getByText('Third publication from page two')).toBeInTheDocument(),
    { timeout: 5000 },
  );

  expect(screen.queryByText('First publication about routing')).not.toBeInTheDocument();
  expect(document.querySelectorAll('.de-pub-card-expanded')).toHaveLength(0);
  expect(toggleIn('Third publication from page two')).toHaveAttribute('aria-expanded', 'false');
});
