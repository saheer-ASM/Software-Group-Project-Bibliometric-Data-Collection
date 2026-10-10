// Opening a saved publication from My Library, and its parity with the Data
// Explorer's publication card.
import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Library from './Library';
import DataExplorer from './DataExplorer';

jest.mock('recharts', () => ({
  ResponsiveContainer: ({ children }) => children,
  LineChart: () => null, Line: () => null, XAxis: () => null, YAxis: () => null,
  CartesianGrid: () => null, Tooltip: () => null, Legend: () => null,
}));

const USER = { id: 'user-1', email: 'u@example.com' };
const KEY = 'scholarMetricsLibrary:user-1';
const AUTHOR_ID = 'A5050585435';

// A full record exactly as /api/search/publications returns it.
const record = (n, extra = {}) => ({
  id: `W${100000 + n}`,
  title: `Routing study number ${n}`,
  abstract: `Abstract of study ${n}.`,
  source: 'IEEE Transactions on Networking',
  fields: ['Computer Networks and Communications'],
  fieldDetails: [{ name: 'Computer Networks and Communications', weight: 0.901 }, { name: 'Signal Processing', weight: 0.099 }],
  authors: [
    { id: AUTHOR_ID, name: 'Shehan Wijesekara', weight: 0.6666, position: 1 },
    { id: 'A2', name: 'Subodha Gunawardena', weight: 0.3333, position: 2 },
  ],
  authorContributionWeight: 0.6666,
  authorOrdering: 'Alphabetical',
  selfCitations: 6,
  averageIsc: 0.802,
  publishedYear: 2023,
  totalCitations: 22,
  rawCitations: 22,
  adjustedCitations: 11.461,
  citingPaperCount: 22,
  ...extra,
});
const reference = (pub) => ({
  id: pub.id, title: pub.title, publishedYear: pub.publishedYear,
  authorId: AUTHOR_ID, authorName: 'Shehan Wijesekara', savedAt: new Date().toISOString(),
});

function seed(library) {
  localStorage.setItem(KEY, JSON.stringify({
    savedAuthors: [], savedPapers: [], recentAuthors: [], collections: [], ...library,
  }));
}

// Serves single-publication lookups from `records`, keyed by pub id.
function serve(records) {
  global.fetch = jest.fn((url) => {
    const href = String(url);
    if (href.includes('/api/search/publications')) {
      const pubId = new URL(href, 'http://x').searchParams.get('pubId');
      const found = records[pubId];
      return Promise.resolve({
        ok: true, status: 200,
        json: async () => ({ publications: found ? [found] : [], pagination: { page: 1, limit: 20, total: found ? 1 : 0 } }),
      });
    }
    return Promise.resolve({ ok: false, status: 404, json: async () => ({}) });
  });
}

const renderLibrary = (onOpenAuthor = jest.fn()) => {
  render(<MemoryRouter><Library user={USER} onOpenAuthor={onOpenAuthor} /></MemoryRouter>);
  return onOpenAuthor;
};
const dialog = () => screen.getByRole('dialog', { name: 'Publication details' });
// Resolves once the dialog holds the loaded card (waitFor retries until it stops throwing).
const findCard = () => waitFor(() => {
  const card = dialog().querySelector('.de-pub-card');
  if (!card) throw new Error('card not loaded yet');
  return card;
});
const openPaper = (title) => fireEvent.click(screen.getByRole('button', { name: `Open details for ${title}` }));
const lookups = () => global.fetch.mock.calls
  .map(([url]) => new URL(String(url), 'http://x'))
  .filter((url) => url.pathname.endsWith('/api/search/publications'))
  .map((url) => `${url.searchParams.get('authorId')}/${url.searchParams.get('pubId')}`);

beforeEach(() => localStorage.clear());
afterEach(() => { delete global.fetch; });

test('clicking a saved publication opens its details, loaded by id for its author', async () => {
  const pub = record(1);
  seed({ savedPapers: [reference(pub)], collections: [{ id: 'c1', name: 'Thesis', paperIds: [pub.id] }] });
  serve({ [pub.id]: pub });
  renderLibrary();

  openPaper(pub.title);

  expect(within(dialog()).getByRole('status')).toHaveTextContent('Loading publication');
  const card = await findCard();
  expect(lookups()).toEqual([`${AUTHOR_ID}/${pub.id}`]);
  expect(within(card).getByRole('heading', { name: pub.title })).toBeInTheDocument();
  expect(within(card).getByText('Read abstract')).toBeInTheDocument();
  expect(within(card).getByText('Abstract of study 1.')).toBeInTheDocument();
  expect(within(card).getByText('IEEE Transactions on Networking')).toBeInTheDocument();
  expect(within(card).getByText('11.461')).toBeInTheDocument();
  expect(within(card).getByText('Thesis')).toBeInTheDocument(); // the collection it is in
  expect(within(card).getByRole('button', { name: /Saved/ })).toBeInTheDocument();
});

test('similar titles: the clicked paper is the one loaded', async () => {
  const a = record(1, { title: 'Deep routing' });
  const b = record(2, { title: 'Deep routing ' });
  seed({ savedPapers: [reference(a), reference({ ...b, title: 'Deep routing (2)' })] });
  serve({ [a.id]: a, [b.id]: b });
  renderLibrary();

  openPaper('Deep routing (2)');
  await waitFor(() => expect(dialog().querySelector('.de-pub-card')).not.toBeNull());
  expect(lookups()).toEqual([`${AUTHOR_ID}/${b.id}`]);
});

test('publications open correctly from different collections', async () => {
  const a = record(1);
  const b = record(2);
  seed({
    savedPapers: [reference(a), reference(b)],
    collections: [{ id: 'c1', name: 'Thesis', paperIds: [a.id] }, { id: 'c2', name: 'Teaching', paperIds: [b.id] }],
  });
  serve({ [a.id]: a, [b.id]: b });
  renderLibrary();

  fireEvent.click(screen.getByRole('button', { name: /^Teaching/ }));
  expect(screen.queryByRole('button', { name: `Open details for ${a.title}` })).not.toBeInTheDocument();
  openPaper(b.title);
  const card = await findCard();
  expect(within(card).getByRole('heading', { name: b.title })).toBeInTheDocument();
  expect(within(card).getByText('Teaching')).toBeInTheDocument();
  expect(lookups()).toEqual([`${AUTHOR_ID}/${b.id}`]);
});

test('closing returns to the same collection with focus on the paper', async () => {
  const a = record(1);
  const b = record(2);
  seed({
    savedPapers: [reference(a), reference(b)],
    collections: [{ id: 'c1', name: 'Thesis', paperIds: [a.id] }, { id: 'c2', name: 'Teaching', paperIds: [b.id] }],
  });
  serve({ [a.id]: a, [b.id]: b });
  renderLibrary();

  fireEvent.click(screen.getByRole('button', { name: /^Teaching/ }));
  openPaper(b.title);
  await waitFor(() => expect(dialog().querySelector('.de-pub-card')).not.toBeNull());

  fireEvent.click(within(dialog()).getByRole('button', { name: 'Close' }));
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: /^Teaching/ })).toHaveClass('active');
  expect(screen.getByRole('button', { name: `Open details for ${b.title}` })).toHaveFocus();

  // Escape closes too.
  openPaper(b.title);
  await waitFor(() => expect(dialog().querySelector('.de-pub-card')).not.toBeNull());
  fireEvent.keyDown(document, { key: 'Escape' });
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
});

test('incomplete metadata is shown gracefully', async () => {
  const sparse = record(1, {
    abstract: '', source: '', fieldDetails: [], fields: [], authors: [],
    publishedYear: null, authorContributionWeight: 0, authorOrdering: 'Unknown',
  });
  seed({ savedPapers: [reference(sparse)] });
  serve({ [sparse.id]: sparse });
  renderLibrary();

  openPaper(sparse.title);
  const card = await findCard();
  expect(within(card).queryByText('Read abstract')).not.toBeInTheDocument();
  expect(within(card).getByText('Year unavailable')).toBeInTheDocument();
  expect(within(card).getByText('0 authors')).toBeInTheDocument();
  expect(within(card).getAllByText('Not calculated').length).toBeGreaterThan(0);
});

test('a saved paper that is no longer in the database says so', async () => {
  const gone = record(1);
  seed({ savedPapers: [reference(gone)] });
  serve({});
  renderLibrary();
  openPaper(gone.title);
  expect(await within(dialog()).findByRole('alert')).toHaveTextContent('no longer available');
});

test('a legacy saved paper without its author explains instead of requesting', async () => {
  const legacy = { id: 'W1', title: 'Old save', publishedYear: 2019, authorId: '', authorName: '' };
  seed({ savedPapers: [legacy] });
  serve({});
  renderLibrary();
  openPaper('Old save');
  expect(await within(dialog()).findByRole('alert')).toHaveTextContent('saved without the author');
  expect(global.fetch).not.toHaveBeenCalled();
});

test('a failed load can be retried', async () => {
  const pub = record(1);
  seed({ savedPapers: [reference(pub)] });
  serve({ [pub.id]: pub });
  const working = global.fetch;
  global.fetch = jest.fn()
    .mockRejectedValueOnce(new TypeError('Failed to fetch'))
    .mockImplementation(working);
  renderLibrary();

  openPaper(pub.title);
  expect(await within(dialog()).findByRole('alert')).toHaveTextContent('Failed to fetch');
  fireEvent.click(within(dialog()).getByRole('button', { name: 'Try again' }));
  await waitFor(() => expect(dialog().querySelector('.de-pub-card')).not.toBeNull());
});

test('an author in the details opens that author, by id', async () => {
  const pub = record(1);
  seed({ savedPapers: [reference(pub)] });
  serve({ [pub.id]: pub });
  const onOpenAuthor = renderLibrary();
  openPaper(pub.title);
  const card = await findCard();
  fireEvent.click(within(card).getByRole('button', { name: /Subodha Gunawardena/ }));
  expect(onOpenAuthor).toHaveBeenCalledWith({ id: 'A2', name: 'Subodha Gunawardena' });
});

test('the card’s Saved button removes the paper, and Save paper puts it back in its collection', async () => {
  const pub = record(1);
  const collections = [{ id: 'c1', name: 'Thesis', paperIds: [pub.id] }];
  seed({ savedPapers: [reference(pub)], collections });
  serve({ [pub.id]: pub }); // signed out: changes stay local, no token
  renderLibrary();
  openPaper(pub.title);
  const card = await findCard();

  fireEvent.click(within(card).getByRole('button', { name: /Saved/ }));
  await waitFor(() => expect(within(card).getByRole('button', { name: /Save paper/ })).toBeInTheDocument());
  expect(JSON.parse(localStorage.getItem(KEY)).savedPapers).toEqual([]);

  fireEvent.click(within(card).getByRole('button', { name: /Save paper/ }));
  await waitFor(() => expect(within(card).getByRole('button', { name: /Saved/ })).toBeInTheDocument());
  const stored = JSON.parse(localStorage.getItem(KEY));
  expect(stored.savedPapers.map((p) => p.id)).toEqual([pub.id]);
  expect(stored.collections).toEqual(collections);
});

test('papers can be removed from the list; the count shows the 200 limit', async () => {
  const a = record(1);
  const b = record(2);
  seed({ savedPapers: [reference(a), reference(b)], collections: [{ id: 'c1', name: 'Thesis', paperIds: [a.id, b.id] }] });
  serve({});
  renderLibrary();

  expect(screen.getByLabelText('2 of 200 saved')).toHaveTextContent('(2/200)');
  fireEvent.click(screen.getByRole('button', { name: `Remove ${a.title} from saved publications` }));
  await waitFor(() => expect(screen.getByLabelText('1 of 200 saved')).toBeInTheDocument());
  const stored = JSON.parse(localStorage.getItem(KEY));
  expect(stored.collections).toEqual([{ id: 'c1', name: 'Thesis', paperIds: [b.id] }]);
});

// ---- Parity with the Data Explorer ------------------------------------------

const shell = (ui) => <MemoryRouter initialEntries={['/data-explorer']}>{ui}</MemoryRouter>;

function cardText(card, label) {
  return card.textContent.replace(label, '').replace(/\s+/g, ' ').trim();
}
function cardControls(card) {
  return [...card.querySelectorAll('button, summary')].map((el) => el.textContent.replace(/\s+/g, ' ').trim());
}

test('the details match the Data Explorer card for the same publication', async () => {
  const pub = record(7);
  seed({ savedPapers: [reference(pub)], collections: [{ id: 'c1', name: 'Thesis', paperIds: [pub.id] }] });

  // 1. The publication as the Data Explorer lists it for this author.
  global.fetch = jest.fn().mockResolvedValue({
    ok: true,
    json: async () => ({
      authorId: AUTHOR_ID, author: 'Shehan Wijesekara', totalPublications: 1, totalCitations: 22,
      totalSelfCitations: 6, totalAdjustedCitations: 11.461, nmIndex: 99.947, hIndex: 1, cScore: 10,
      careerCompensation: 1, trendData: [], publications: [pub],
      publicationsPagination: { page: 1, limit: 20, total: 1, totalPages: 1, hasNextPage: false, hasPreviousPage: false },
      publicationFacets: { years: [2023], fields: ['Computer Networks and Communications'] },
    }),
  });
  const explorer = render(shell(<DataExplorer authorName="Shehan Wijesekara" user={USER} />));
  const explorerCard = (await screen.findByRole('heading', { name: pub.title })).closest('.de-pub-card');
  const explorerText = cardText(explorerCard, 'Paper 01');
  const explorerControls = cardControls(explorerCard).filter((t) => t !== 'Paper 01');
  explorer.unmount();

  // 2. The same publication opened from My Library.
  serve({ [pub.id]: pub });
  render(shell(<Library user={USER} onOpenAuthor={jest.fn()} />));
  openPaper(pub.title);
  const libraryCard = await waitFor(() => {
    const card = dialog().querySelector('.de-pub-card');
    if (!card) throw new Error('not yet');
    return card;
  });

  expect(cardText(libraryCard, 'Thesis')).toBe(explorerText);
  expect(cardControls(libraryCard)).toEqual(explorerControls);
  // Same component, same structure: every section class is present in both.
  for (const selector of ['.de-pub-meta', '.de-pub-abstract', '.de-pub-details-toggle', '.de-pub-fields', '.de-pub-authors', '.de-pub-stats']) {
    expect(libraryCard.querySelector(selector)).not.toBeNull();
  }
});

test('Data Explorer: Save paper still opens the collection dialog, and warns at the limit', async () => {
  const pub = record(3);
  const full = Array.from({ length: 200 }, (_, i) => reference(record(1000 + i)));
  seed({ savedPapers: full });
  global.fetch = jest.fn().mockResolvedValue({
    ok: true,
    json: async () => ({
      authorId: AUTHOR_ID, author: 'Shehan Wijesekara', totalPublications: 1, totalCitations: 22,
      totalSelfCitations: 6, totalAdjustedCitations: 11.461, nmIndex: 99.947, hIndex: 1, cScore: 10,
      careerCompensation: 1, trendData: [], publications: [pub],
      publicationsPagination: { page: 1, limit: 20, total: 1, totalPages: 1, hasNextPage: false, hasPreviousPage: false },
      publicationFacets: { years: [2023], fields: [] },
    }),
  });
  render(shell(<DataExplorer authorName="Shehan Wijesekara" user={USER} />));
  const card = (await screen.findByRole('heading', { name: pub.title })).closest('.de-pub-card');

  fireEvent.click(within(card).getByRole('button', { name: /Save paper/ }));
  const saveDialog = screen.getByRole('dialog', { name: 'Choose a collection' });
  expect(within(saveDialog).getByRole('alert')).toHaveTextContent('up to 200 publications');
  expect(within(saveDialog).getByRole('button', { name: /Save to collection/ })).toBeDisabled();
});

test('mobile: the close button stays outside the scrolling body, so it cannot scroll away', async () => {
  const pub = record(9);
  seed({ savedPapers: [reference(pub)] });
  serve({ [pub.id]: pub });
  renderLibrary();
  openPaper(pub.title);
  const card = await findCard();

  const body = dialog().querySelector('.de-publication-dialog-body');
  const close = within(dialog()).getByRole('button', { name: 'Close' });
  // The card (abstract, Show Details) scrolls inside the body; the header and
  // its close button are not part of what scrolls.
  expect(body.contains(card)).toBe(true);
  expect(body.contains(close)).toBe(false);

  // Opening the abstract and Show Details changes the body only.
  fireEvent.click(within(card).getByText('Read abstract'));
  fireEvent.click(within(card).getByRole('button', { name: /Show Details/ }));
  expect(within(card).getByRole('button', { name: /Hide Details/ })).toBeInTheDocument();
  expect(body.contains(close)).toBe(false);
  expect(close).toBeVisible();
});
