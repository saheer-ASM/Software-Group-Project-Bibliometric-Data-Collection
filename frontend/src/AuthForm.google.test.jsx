import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import AuthForm from './AuthForm';

// "Continue with Google" decision logic: Sign In explains, Register registers.
const mockGoogleUser = { uid: 'g-1', email: 'someone@gmail.com', photoURL: '', emailVerified: false, getIdToken: jest.fn() };

jest.mock('firebase/auth', () => ({
  signOut: jest.fn(),
  reload: jest.fn(),
}));

jest.mock('./firebase', () => ({
  auth: { currentUser: null },
  missingConfig: [],
  registerWithEmail: jest.fn(),
  sendVerificationEmail: jest.fn(),
  signInWithGoogle: jest.fn(),
  googleCredentialFromError: jest.fn(),
}));

jest.mock('./services/registrationService', () => ({
  RESEND_COOLDOWN_S: 60,
  getRegistrationState: jest.fn(),
}));

const firebase = require('./firebase');
const firebaseAuth = require('firebase/auth');
const { getRegistrationState } = require('./services/registrationService');

const MISLEADING = /verify your email address before logging in/i;

const renderForm = (mode) => {
  const onLogin = jest.fn();
  const onNavigate = jest.fn();
  const utils = render(<AuthForm mode={mode} onLogin={onLogin} onNavigate={onNavigate} />);
  return { onLogin, onNavigate, ...utils };
};

// Each page has its own Google button; pick the one in the visible panel.
const clickGoogle = (container, mode) => {
  const panel = container.querySelector(mode === 'register' ? '.form-box.register' : '.form-box.login');
  fireEvent.click(panel.querySelector('.google-btn'));
};

beforeEach(() => {
  firebase.auth.currentUser = mockGoogleUser;
  mockGoogleUser.emailVerified = false;
  firebase.signInWithGoogle.mockResolvedValue({ user: mockGoogleUser });
  firebase.sendVerificationEmail.mockResolvedValue();
  firebaseAuth.signOut.mockResolvedValue();
  firebaseAuth.reload.mockResolvedValue();
  localStorage.clear();
  window.alert = jest.fn();
  window.confirm = jest.fn();
});

afterEach(() => {
  expect(window.alert).not.toHaveBeenCalled();
  expect(window.confirm).not.toHaveBeenCalled();
});

test('Sign In + never-registered Google account -> "No ScholarMetrics account found" + Create Account, no registration steps', async () => {
  getRegistrationState.mockResolvedValue({ status: 'NOT_REGISTERED' });
  const { onNavigate, container } = renderForm('login');
  clickGoogle(container, 'login');

  expect(await screen.findByText('No ScholarMetrics account found.')).toBeInTheDocument();
  expect(screen.getByText(/This Google account is not registered with ScholarMetrics/)).toBeInTheDocument();
  expect(getRegistrationState).toHaveBeenCalledWith(mockGoogleUser, 'signin');
  expect(firebaseAuth.signOut).toHaveBeenCalled();
  expect(onNavigate).not.toHaveBeenCalledWith('/complete-profile', expect.anything());

  fireEvent.click(screen.getByRole('button', { name: 'Create Account' }));
  expect(onNavigate).toHaveBeenCalledWith('/register');
});

test('Sign In + incomplete registration -> "Your registration is not complete" + Continue Registration', async () => {
  const registration = { status: 'INCOMPLETE', step: 'password', profile: { username: 'S', email: 'someone@gmail.com', designation: 'Lecturer' } };
  getRegistrationState.mockResolvedValue(registration);
  const { onNavigate, onLogin, container } = renderForm('login');
  clickGoogle(container, 'login');

  expect(await screen.findByText('Your registration is not complete.')).toBeInTheDocument();
  expect(screen.getByText(/complete your registration and verify your email address before signing in/)).toBeInTheDocument();
  expect(screen.queryByText(MISLEADING)).not.toBeInTheDocument();
  expect(onNavigate).not.toHaveBeenCalled(); // explained first, not pushed into the steps
  expect(firebaseAuth.signOut).not.toHaveBeenCalled(); // session kept so it can resume
  expect(onLogin).not.toHaveBeenCalled();

  fireEvent.click(screen.getByRole('button', { name: 'Continue Registration' }));
  expect(onNavigate).toHaveBeenCalledWith('/complete-profile', { registration });
});

test('Sign In + verification pending -> instructions with Inbox/Spam/Junk, resend with cooldown, continue', async () => {
  const registration = { status: 'VERIFICATION_PENDING', step: 'verify', profile: { username: 'S', email: 'someone@gmail.com', designation: 'Lecturer' } };
  getRegistrationState.mockResolvedValue(registration);
  const { onNavigate, container } = renderForm('login');
  clickGoogle(container, 'login');

  expect(await screen.findByText('Email verification required.')).toBeInTheDocument();
  expect(screen.getByText('someone@gmail.com')).toBeInTheDocument();
  expect(screen.getByText(/Spam\/Junk/)).toBeInTheDocument();

  fireEvent.click(screen.getByRole('button', { name: 'Resend Verification Email' }));
  expect(await screen.findByText('Verification email sent again. Please check your inbox and Spam/Junk folder.')).toBeInTheDocument();
  expect(firebaseAuth.reload).toHaveBeenCalledWith(mockGoogleUser);
  expect(firebase.sendVerificationEmail).toHaveBeenCalledWith(mockGoogleUser, '/complete-profile');
  expect(screen.getByRole('button', { name: /Resend Verification Email \(\d+s\)/ })).toBeDisabled();

  fireEvent.click(screen.getByRole('button', { name: 'Continue Registration' }));
  expect(onNavigate).toHaveBeenCalledWith('/complete-profile', { registration });
});

test('Sign In + completed account -> straight to the Dashboard', async () => {
  getRegistrationState.mockResolvedValue({ status: 'COMPLETED', token: 'jwt', user: { id: 'g-1', username: 'S' } });
  const { onLogin, container } = renderForm('login');
  clickGoogle(container, 'login');
  await waitFor(() => expect(onLogin).toHaveBeenCalledWith(expect.objectContaining({ id: 'g-1' })));
  expect(localStorage.getItem('token')).toBe('jwt');
});

test('Register + new Google account -> registration flow opens', async () => {
  const registration = { status: 'INCOMPLETE', step: 'profile', profile: { username: 'S', email: 'someone@gmail.com', designation: '' } };
  getRegistrationState.mockResolvedValue(registration);
  const { onNavigate, container } = renderForm('register');
  clickGoogle(container, 'register');
  await waitFor(() => expect(onNavigate).toHaveBeenCalledWith('/complete-profile', { registration }));
  expect(getRegistrationState).toHaveBeenCalledWith(mockGoogleUser, 'register');
});

test('Register + already-completed Google account -> Dashboard, no registration steps', async () => {
  getRegistrationState.mockResolvedValue({ status: 'COMPLETED', token: 'jwt', user: { id: 'g-1' } });
  const { onLogin, onNavigate, container } = renderForm('register');
  clickGoogle(container, 'register');
  await waitFor(() => expect(onLogin).toHaveBeenCalled());
  expect(onNavigate).not.toHaveBeenCalledWith('/complete-profile', expect.anything());
});
