// Leaving the Data Explorer and coming back -- from the menu, or after a
// refresh -- reopens the exact author last viewed there.
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import App from './App';

jest.mock('recharts', () => ({
  ResponsiveContainer: ({ children }) => children,
  LineChart: () => null, Line: () => null, XAxis: () => null, YAxis: () => null,
  CartesianGrid: () => null, Tooltip: () => null, Legend: () => null,
}));

const AUTHORS = { A1: 'Ada Lovelace', A2: 'Alan Turing' };
const profileFor = (id) => ({
  authorId: id, author: AUTHORS[id], totalPublications: 0, totalCitations: 0,
  totalSelfCitations: 0, totalAdjustedCitations: 0, nmIndex: 0, hIndex: 0, cScore: 0,
  careerCompensation: 0, trendData: [], publications: [],
  publicationsPagination: { page: 1, limit: 20, total: 0, totalPages: 0, hasNextPage: false, hasPreviousPage: false },
  publicationFacets: { years: [], fields: [] },
});

let searches; // the /api/search requests, as URLSearchParams

beforeEach(() => {
  searches = [];
  sessionStorage.clear();
  localStorage.clear();
  localStorage.setItem('token', 'session-token');
  global.fetch = jest.fn(async (url) => {
    const href = new URL(String(url), 'http://localhost');
    const reply = (body) => ({ ok: true, status: 200, json: async () => body });
    if (href.pathname === '/api/auth/profile') {
      return reply({ id: 'u1', username: 'Test User', email: 'test@example.com', designation: 'Researcher' });
    }
    if (href.pathname === '/api/search') {
      searches.push(href.searchParams);
      const id = href.searchParams.get('authorId')
        || Object.keys(AUTHORS).find((key) => AUTHORS[key] === href.searchParams.get('author'));
      return reply(profileFor(id));
    }
    if (href.pathname === '/api/search/publications') {
      return reply({ publications: [], pagination: profileFor('A1').publicationsPagination });
    }
    if (href.pathname === '/api/authors') return reply([]);
    return reply({});
  });
});

afterEach(() => { delete global.fetch; });

const Location = () => {
  const { pathname, search } = useLocation();
  return <span data-testid="location">{pathname + search}</span>;
};

const renderAt = (path) => render(
  <MemoryRouter initialEntries={[path]}>
    <App />
    <Location />
  </MemoryRouter>,
);

const location = () => screen.getByTestId('location').textContent;
const menu = (name) => screen.getAllByRole('link', { name })[0];
const lastSearch = () => searches[searches.length - 1];

// The address gets the authorId only once the page has loaded and reported
// that author.
const waitForAuthorOnScreen = (id) => waitFor(() => expect(location()).toContain(`authorId=${id}`));

test('the menu reopens the last author viewed, by id', async () => {
  renderAt('/data-explorer?author=Ada%20Lovelace'); // a name only, e.g. typed on the Dashboard
  await waitForAuthorOnScreen('A1');

  fireEvent.click(menu('Dashboard'));
  await waitFor(() => expect(location()).toBe('/dashboard'));
  fireEvent.click(menu('Data Explorer'));

  await waitFor(() => expect(location()).toMatch(/^\/data-explorer\?/));
  await waitFor(() => expect(lastSearch().get('authorId')).toBe('A1'));
});

test('an author searched inside the Data Explorer is the one reopened', async () => {
  renderAt('/data-explorer?author=Ada%20Lovelace');
  await waitForAuthorOnScreen('A1');

  const box = screen.getByRole('combobox', { name: 'Search another researcher' });
  fireEvent.change(box, { target: { value: 'Alan Turing' } });
  fireEvent.submit(box.closest('form'));
  await waitForAuthorOnScreen('A2');

  fireEvent.click(menu('Dashboard'));
  await waitFor(() => expect(location()).toBe('/dashboard'));
  fireEvent.click(menu('Data Explorer'));
  await waitFor(() => expect(lastSearch().get('authorId')).toBe('A2'));
});

test('after a refresh, the menu still reopens the last author viewed', async () => {
  const first = renderAt('/data-explorer?author=Ada%20Lovelace');
  await waitForAuthorOnScreen('A1');
  first.unmount(); // a refresh: the app starts over, the tab's storage stays

  renderAt('/dashboard');
  fireEvent.click((await screen.findAllByRole('link', { name: 'Data Explorer' }))[0]);
  await waitFor(() => expect(lastSearch().get('authorId')).toBe('A1'));
});

test('logging out forgets the author', async () => {
  renderAt('/data-explorer?author=Ada%20Lovelace');
  await waitForAuthorOnScreen('A1');
  expect(sessionStorage.getItem('lastViewedAuthor')).toContain('A1');

  fireEvent.click(screen.getByRole('button', { name: 'Logout' }));
  await waitFor(() => expect(location()).toBe('/login'));
  expect(sessionStorage.getItem('lastViewedAuthor')).toBeNull();
});

test('another account in the same tab does not reopen it', async () => {
  sessionStorage.setItem('lastViewedAuthor', JSON.stringify({ userId: 'someone-else', id: 'A2', name: 'Alan Turing' }));
  renderAt('/dashboard');
  fireEvent.click((await screen.findAllByRole('link', { name: 'Data Explorer' }))[0]);
  await waitFor(() => expect(location()).toBe('/data-explorer'));
  expect(searches).toHaveLength(0);
});
