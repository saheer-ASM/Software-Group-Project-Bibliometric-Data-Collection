import { render, screen } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import App from './App';

// Shows the router's current path so tests can assert redirects.
const CurrentPath = () => <span data-testid="path">{useLocation().pathname}</span>;

const renderAt = (path) => render(
  <MemoryRouter initialEntries={[path]}>
    <App />
    <CurrentPath />
  </MemoryRouter>,
);

beforeEach(() => localStorage.clear());

test.each(['/dashboard', '/data-explorer', '/settings', '/about', '/library', '/admin'])(
  'signed-out visit to %s redirects to /login',
  async (path) => {
    renderAt(path);
    expect(await screen.findByTestId('path')).toHaveTextContent(/^\/login$/);
    expect(screen.getByRole('heading', { name: 'Login' })).toBeInTheDocument();
  },
);

test('/ and unknown paths go to /login when signed out', async () => {
  renderAt('/no-such-page');
  expect(await screen.findByTestId('path')).toHaveTextContent(/^\/login$/);
});

test('/register shows the registration form', async () => {
  renderAt('/register');
  expect(await screen.findByRole('heading', { name: 'Registration' })).toBeInTheDocument();
  expect(screen.getByTestId('path')).toHaveTextContent('/register');
});

test('/forgot-password shows the reset-password form', async () => {
  renderAt('/forgot-password');
  expect(await screen.findByRole('heading', { name: 'Reset Password' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Send Reset Link' })).toBeInTheDocument();
});

test('/verify-email without a pending registration shows its fallback', async () => {
  renderAt('/verify-email');
  expect(await screen.findByRole('heading', { name: 'No pending verification' })).toBeInTheDocument();
});
