import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Library from './Library';

const USER = { id: 'user-1', email: 'u@example.com' };
const KEY = 'scholarMetricsLibrary:user-1';
const author = (n) => ({ id: `A${1000 + n}`, name: `Author ${n}` });
const ago = (ms) => new Date(Date.now() - ms).toISOString();

function seed(library) {
  localStorage.setItem(KEY, JSON.stringify({
    savedAuthors: [], savedPapers: [], recentAuthors: [], collections: [], ...library,
  }));
}

function renderLibrary(onOpenAuthor = jest.fn()) {
  render(<MemoryRouter><Library user={USER} onOpenAuthor={onOpenAuthor} /></MemoryRouter>);
  return onOpenAuthor;
}

const panel = (name) => screen.getByRole('heading', { name }).closest('section');

beforeEach(() => {
  localStorage.clear();
  global.fetch = jest.fn();
});
afterEach(() => { delete global.fetch; });

test('saved authors show their count against the 100 limit', () => {
  seed({ savedAuthors: Array.from({ length: 35 }, (_, i) => ({ ...author(i), savedAt: ago(i) })) });
  renderLibrary();
  expect(screen.getByLabelText('35 of 100 saved')).toHaveTextContent('(35/100)');
});

test('opening a saved author passes its id, not just its name', () => {
  seed({ savedAuthors: [{ ...author(1), savedAt: ago(0) }] });
  const onOpenAuthor = renderLibrary();
  fireEvent.click(within(panel(/Saved authors/)).getByText('Author 1'));
  expect(onOpenAuthor).toHaveBeenCalledWith({ id: 'A1001', name: 'Author 1' });
});

test('recently viewed shows the latest 20, with the full history on request', () => {
  seed({ recentAuthors: Array.from({ length: 45 }, (_, i) => ({ ...author(i), viewedAt: ago(i * 1000) })) });
  renderLibrary();
  const recent = panel(/Recently viewed/);

  expect(within(recent).getAllByRole('button', { name: /^Remove .* from recently viewed$/ })).toHaveLength(20);
  expect(within(recent).getByText('Latest 20 of 45')).toBeInTheDocument();
  // Newest first.
  expect(within(recent).getAllByText(/^Author \d+$/)[0]).toHaveTextContent('Author 0');

  fireEvent.click(within(recent).getByRole('button', { name: 'Full history (45)' }));
  expect(within(recent).getAllByRole('button', { name: /^Remove .* from recently viewed$/ })).toHaveLength(45);

  fireEvent.click(within(recent).getByRole('button', { name: 'Show latest' }));
  expect(within(recent).getAllByRole('button', { name: /^Remove .* from recently viewed$/ })).toHaveLength(20);
});

test('no full-history toggle when there are 20 or fewer', () => {
  seed({ recentAuthors: Array.from({ length: 5 }, (_, i) => ({ ...author(i), viewedAt: ago(i) })) });
  renderLibrary();
  expect(screen.queryByRole('button', { name: /Full history/ })).not.toBeInTheDocument();
  expect(screen.getByText('Last 30 days')).toBeInTheDocument();
});

test('expired history is not displayed', () => {
  seed({
    recentAuthors: [
      { ...author(1), viewedAt: ago(1000) },
      { ...author(2), viewedAt: ago(31 * 24 * 60 * 60 * 1000) },
    ],
  });
  renderLibrary();
  expect(screen.getByText('Author 1')).toBeInTheDocument();
  expect(screen.queryByText('Author 2')).not.toBeInTheDocument();
});

test('clear history asks first, then empties the list', async () => {
  seed({ recentAuthors: [{ ...author(1), viewedAt: ago(0) }] });
  renderLibrary();

  fireEvent.click(screen.getByRole('button', { name: 'Clear history' }));
  expect(screen.getByText(/Clear your browsing history\?/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
  expect(screen.getByText('Author 1')).toBeInTheDocument();

  fireEvent.click(screen.getByRole('button', { name: 'Clear history' }));
  fireEvent.click(screen.getByRole('button', { name: 'Clear' }));
  await waitFor(() => expect(screen.queryByText('Author 1')).not.toBeInTheDocument());
  expect(screen.getByText('Viewed researchers will appear here.')).toBeInTheDocument();
});

test('a failed removal is reported and the author stays', async () => {
  localStorage.setItem('token', 'test-token');
  seed({ savedAuthors: [{ ...author(1), savedAt: ago(0) }] });
  fetch.mockResolvedValueOnce({ ok: false, status: 500, json: async () => ({ message: 'Unable to remove this author.' }) });
  renderLibrary();

  fireEvent.click(screen.getByRole('button', { name: 'Remove Author 1 from saved authors' }));

  expect(await screen.findByRole('alert')).toHaveTextContent('Unable to remove this author.');
  expect(within(panel(/Saved authors/)).getByText('Author 1')).toBeInTheDocument();
});

test('empty states', () => {
  renderLibrary();
  expect(screen.getByText('Save an author from their Data Explorer profile.')).toBeInTheDocument();
  expect(screen.getByText('Viewed researchers will appear here.')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Clear history' })).not.toBeInTheDocument();
  expect(screen.getByLabelText('0 of 100 saved')).toHaveTextContent('(0/100)');
});
