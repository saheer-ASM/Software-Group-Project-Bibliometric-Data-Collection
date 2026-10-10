// Author-name search on the Dashboard and in the Data Explorer: limits,
// trimming, Unicode, debouncing and avoiding needless requests.
import React from 'react';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Dashboard from './Dashboard';
import DataExplorer from './DataExplorer';
import { clearAuthorSuggestionCache, normalizeAuthorQuery, isSearchableAuthorQuery } from './services/authorSearch';

jest.mock('recharts', () => ({
  ResponsiveContainer: ({ children }) => children,
  LineChart: () => null, Line: () => null, XAxis: () => null, YAxis: () => null,
  CartesianGrid: () => null, Tooltip: () => null, Legend: () => null,
}));

const calls = (path) => global.fetch.mock.calls
  .map(([url]) => new URL(String(url), 'http://x'))
  .filter((url) => url.pathname === path);
const suggestionQueries = () => calls('/api/authors').map((url) => url.searchParams.get('q'));

beforeEach(() => {
  jest.useFakeTimers();
  clearAuthorSuggestionCache();
  global.fetch = jest.fn((url) => {
    const href = String(url);
    const body = href.includes('/api/authors') ? [{ id: 'A1', name: 'Yi’ang Li' }] : {};
    return Promise.resolve({ ok: !href.includes('/api/search?'), status: 200, json: async () => body });
  });
});
afterEach(() => {
  jest.useRealTimers();
  delete global.fetch;
});

// Advance the clock and let the resulting fetch promises settle.
const wait = (ms) => act(async () => { jest.advanceTimersByTime(ms); });

describe('shared rules', () => {
  test('trimming and the 2..200 window', () => {
    expect(normalizeAuthorQuery('  Li  ')).toBe('Li');
    for (const q of ['', '   ', 'a', '  a ']) expect(isSearchableAuthorQuery(normalizeAuthorQuery(q))).toBe(false);
    expect(isSearchableAuthorQuery('ab')).toBe(true);
    expect(isSearchableAuthorQuery('a'.repeat(200))).toBe(true);
    expect(isSearchableAuthorQuery('a'.repeat(201))).toBe(false);
  });

  test('international names are untouched apart from NFC normalization', () => {
    for (const name of ['Jorge Martínez-Bauset', "Yi'ang Li", 'J. R. R. Tolkien', '王小明', 'Дмитрий Иванов']) {
      expect(normalizeAuthorQuery(name)).toBe(name);
    }
    expect(normalizeAuthorQuery('Martínez')).toBe('Martínez');
  });
});

describe('Dashboard search', () => {
  const renderDashboard = (onNavigateToExplorer = jest.fn()) => {
    render(<MemoryRouter><Dashboard onNavigateToExplorer={onNavigateToExplorer} /></MemoryRouter>);
    return onNavigateToExplorer;
  };
  const input = () => screen.getByRole('combobox');
  const type = (value) => fireEvent.change(input(), { target: { value } });

  test('input is capped at 200 characters', () => {
    renderDashboard();
    expect(input()).toHaveAttribute('maxLength', '200');
  });

  test('empty, whitespace-only and one-character input sends nothing', async () => {
    renderDashboard();
    for (const value of ['', '    ', 'a', '  a  ']) {
      type(value);
      await wait(1000);
    }
    expect(suggestionQueries()).toEqual([]);
  });

  test('two characters search once, after the debounce, trimmed', async () => {
    renderDashboard();
    type('  Li ');
    await wait(200);
    expect(suggestionQueries()).toEqual([]);
    await wait(100);
    expect(suggestionQueries()).toEqual(['Li']);
  });

  test('typing quickly sends one request for the final text', async () => {
    renderDashboard();
    for (const value of ['Ma', 'Mar', 'Mart', 'Marti']) {
      type(value);
      await wait(100);
    }
    await wait(300);
    expect(suggestionQueries()).toEqual(['Marti']);
  });

  test('unchanged queries are not re-sent (trailing space, reopening, returning to it)', async () => {
    renderDashboard();
    type('Li');
    await wait(300);
    type('Li   '); // trailing whitespace: same query
    await wait(300);
    fireEvent.keyDown(input(), { key: 'Escape' }); // close the list...
    fireEvent.focus(input()); // ...and reopen it
    await wait(300);
    type('Lin');
    await wait(300);
    type('Li'); // back to an earlier query: answered from the cache
    await wait(300);
    expect(suggestionQueries()).toEqual(['Li', 'Lin']);
  });

  test('Unicode input is sent in NFC form', async () => {
    renderDashboard();
    type('Martínez');
    await wait(300);
    expect(suggestionQueries()).toEqual(['Martínez']);
  });

  test('submitting one character explains instead of searching', async () => {
    const navigate = renderDashboard();
    type(' a ');
    fireEvent.submit(input().closest('form'));
    expect(screen.getByRole('alert')).toHaveTextContent('Type at least 2 characters');
    expect(navigate).not.toHaveBeenCalled();
    type('ab');
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  test('a valid name is submitted trimmed, punctuation intact', () => {
    const navigate = renderDashboard();
    type("   Yi'ang Li  ");
    fireEvent.submit(input().closest('form'));
    expect(navigate).toHaveBeenCalledWith("Yi'ang Li");
  });

  test('empty submit does nothing', () => {
    const navigate = renderDashboard();
    type('   ');
    fireEvent.submit(input().closest('form'));
    expect(navigate).not.toHaveBeenCalled();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
});

describe('Data Explorer search', () => {
  const renderExplorer = () => render(<MemoryRouter initialEntries={['/data-explorer']}><DataExplorer /></MemoryRouter>);
  const input = () => document.getElementById('explorer-author-search');
  const type = (value) => fireEvent.change(input(), { target: { value } });

  test('input is capped at 200 characters', () => {
    renderExplorer();
    expect(input()).toHaveAttribute('maxLength', '200');
  });

  test('suggestions: one character sends nothing, two characters send once after the debounce', async () => {
    renderExplorer();
    type('a');
    await wait(1000);
    expect(suggestionQueries()).toEqual([]);
    type(' ab ');
    await wait(300);
    type(' ab      ');
    await wait(300);
    expect(suggestionQueries()).toEqual(['ab']);
  });

  test('submitting one character shows the minimum and never queries the profile', async () => {
    renderExplorer();
    type('a');
    await act(async () => { fireEvent.submit(input().closest('form')); });
    expect(screen.getByText('Type at least 2 characters of the author’s name.')).toBeInTheDocument();
    expect(calls('/api/search')).toEqual([]);
  });

  test('a valid name is looked up trimmed and NFC-normalized', async () => {
    renderExplorer();
    type('  Martínez  ');
    await act(async () => { fireEvent.submit(input().closest('form')); });
    expect(calls('/api/search').map((url) => url.searchParams.get('author'))).toEqual(['Martínez']);
  });
});
