import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import CompleteProfile from './CompleteProfile';

// A signed-in Google user. `emailVerified` is what Firebase reports after reload().
const mockUser = {
  uid: 'google-uid-1',
  email: 'new.user@gmail.com',
  displayName: 'New User',
  emailVerified: true,
  providerData: [{ providerId: 'google.com' }],
};

jest.mock('firebase/auth', () => ({
  onAuthStateChanged: (authArg, cb) => { cb(authArg.currentUser); return () => {}; },
  signOut: jest.fn(),
  updateProfile: jest.fn(),
  reload: jest.fn(),
}));

jest.mock('./firebase', () => ({
  auth: { currentUser: null },
  hasPasswordSignIn: (user) => user.providerData.some((p) => p.providerId === 'password'),
  linkPasswordCredential: jest.fn(),
  refreshEmailVerified: jest.fn(),
  sendVerificationEmail: jest.fn(),
  registerWithEmail: jest.fn(),
}));

jest.mock('./services/registrationService', () => ({
  RESEND_COOLDOWN_S: 60,
  getRegistrationState: jest.fn(),
  saveRegistrationProfile: jest.fn(),
  completeRegistration: jest.fn(),
}));

const firebase = require('./firebase');
const firebaseAuth = require('firebase/auth');
const registration = require('./services/registrationService');

const PROFILE = { username: 'New User', email: 'new.user@gmail.com', designation: '' };
const COMPLETED = { status: 'COMPLETED', token: 'session-jwt', user: { id: 'google-uid-1', username: 'New User', designation: 'Lecturer' } };
const state = (status, step, designation = '') => ({ status, step, profile: { ...PROFILE, designation } });

const renderAt = (initialState) => {
  const onLogin = jest.fn();
  const onNavigate = jest.fn();
  render(<CompleteProfile onLogin={onLogin} onNavigate={onNavigate} initialState={initialState} />);
  return { onLogin, onNavigate };
};

const setPasswords = (password, confirm) => {
  fireEvent.change(screen.getByPlaceholderText('Password'), { target: { value: password } });
  fireEvent.change(screen.getByPlaceholderText('Confirm Password'), { target: { value: confirm } });
  fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
};

const MISLEADING = /verify your email address before logging in/i;

beforeEach(() => {
  // CRA's Jest config resets mock implementations before every test.
  mockUser.providerData = [{ providerId: 'google.com' }];
  mockUser.emailVerified = true;
  firebase.auth.currentUser = mockUser;
  firebaseAuth.updateProfile.mockResolvedValue();
  firebaseAuth.signOut.mockResolvedValue();
  firebaseAuth.reload.mockResolvedValue();
  firebase.sendVerificationEmail.mockResolvedValue();
  firebase.linkPasswordCredential.mockImplementation(async (user) => {
    user.providerData = [...user.providerData, { providerId: 'password' }];
    user.emailVerified = false; // what production Firebase does after linking
    return user;
  });
  registration.saveRegistrationProfile.mockResolvedValue(state('INCOMPLETE', 'password', 'Lecturer'));
  registration.completeRegistration.mockResolvedValue(COMPLETED);
  localStorage.clear();
  window.alert = jest.fn();
});

test('Test 1: new Google user -> designation -> password -> verification email', async () => {
  renderAt(state('INCOMPLETE', 'profile'));

  expect(await screen.findByRole('heading', { name: 'Complete Your Profile' })).toBeInTheDocument();
  expect(screen.getByText('Step 1 of 3')).toBeInTheDocument();
  expect(screen.getByLabelText('Full Name')).toHaveValue('New User');
  expect(screen.getByLabelText('Email')).toHaveAttribute('readonly');

  fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
  expect(await screen.findByText(/Please enter your designation/)).toBeInTheDocument();
  expect(registration.saveRegistrationProfile).not.toHaveBeenCalled();

  fireEvent.change(screen.getByLabelText('Designation'), { target: { value: 'Lecturer' } });
  fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
  expect(await screen.findByRole('heading', { name: 'Set Your Password' })).toBeInTheDocument();
  expect(registration.saveRegistrationProfile).toHaveBeenCalledWith(mockUser, { username: 'New User', designation: 'Lecturer' });

  setPasswords('Strong#Pass1', 'Strong#Pass1');
  expect(await screen.findByRole('heading', { name: 'Check your email' })).toBeInTheDocument();
  expect(firebase.linkPasswordCredential).toHaveBeenCalledWith(mockUser, 'Strong#Pass1');
  expect(firebase.registerWithEmail).not.toHaveBeenCalled(); // no second Firebase user
  expect(firebase.sendVerificationEmail).toHaveBeenCalledWith(mockUser, '/complete-profile');
  expect(screen.queryByText(MISLEADING)).not.toBeInTheDocument();
});

test('Test 2: verification screen explains Inbox, Spam and Junk, with the email shown', async () => {
  renderAt(state('VERIFICATION_PENDING', 'verify', 'Lecturer'));
  expect(await screen.findByRole('heading', { name: 'Check your email' })).toBeInTheDocument();
  expect(screen.getByText('new.user@gmail.com')).toBeInTheDocument();
  expect(screen.getByText(/check your inbox and click the verification link/i)).toBeInTheDocument();
  expect(screen.getByText(/Spam/)).toBeInTheDocument();
  expect(screen.getByText(/Junk/)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: "I've Verified" })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Resend Verification Email' })).toBeEnabled();
});

test("Test 3: I've Verified before verifying -> clear in-page message, no login", async () => {
  firebase.refreshEmailVerified.mockResolvedValue(false);
  const { onLogin } = renderAt(state('VERIFICATION_PENDING', 'verify', 'Lecturer'));
  fireEvent.click(await screen.findByRole('button', { name: "I've Verified" }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Your email has not been verified yet. Please check your inbox and Spam/Junk folder');
  expect(firebase.refreshEmailVerified).toHaveBeenCalledWith(mockUser); // real Firebase reload
  expect(registration.completeRegistration).not.toHaveBeenCalled();
  expect(onLogin).not.toHaveBeenCalled();
});

test("Test 4: verified -> I've Verified -> registration completed -> Dashboard", async () => {
  firebase.refreshEmailVerified.mockResolvedValue(true);
  const { onLogin } = renderAt(state('VERIFICATION_PENDING', 'verify', 'Lecturer'));
  fireEvent.click(await screen.findByRole('button', { name: "I've Verified" }));
  await waitFor(() => expect(onLogin).toHaveBeenCalledWith(COMPLETED.user));
  expect(registration.completeRegistration).toHaveBeenCalledWith(mockUser);
  expect(localStorage.getItem('token')).toBe('session-jwt');
});

test('Test 5/6/7: resuming opens the step the backend reports', async () => {
  registration.getRegistrationState.mockResolvedValueOnce(state('INCOMPLETE', 'password', 'Lecturer'));
  renderAt(undefined); // e.g. page reload: ask the backend
  expect(await screen.findByRole('heading', { name: 'Set Your Password' })).toBeInTheDocument();
  expect(registration.getRegistrationState).toHaveBeenCalledWith(mockUser, 'register');
});

test('resuming at the verification step does not re-send automatically', async () => {
  renderAt(state('VERIFICATION_PENDING', 'verify', 'Lecturer'));
  expect(await screen.findByRole('heading', { name: 'Check your email' })).toBeInTheDocument();
  expect(firebase.sendVerificationEmail).not.toHaveBeenCalled();
});

test('Resend: checks the user is still unverified, sends, confirms, then cools down', async () => {
  mockUser.providerData = [{ providerId: 'google.com' }, { providerId: 'password' }];
  mockUser.emailVerified = false;
  renderAt(state('VERIFICATION_PENDING', 'verify', 'Lecturer'));
  fireEvent.click(await screen.findByRole('button', { name: 'Resend Verification Email' }));
  expect(await screen.findByRole('status')).toHaveTextContent('Verification email sent again. Please check your inbox and Spam/Junk folder.');
  expect(firebaseAuth.reload).toHaveBeenCalledWith(mockUser);
  expect(firebase.sendVerificationEmail).toHaveBeenCalledTimes(1);
  const resend = screen.getByRole('button', { name: /Resend Verification Email \(\d+s\)/ });
  expect(resend).toBeDisabled();
  await act(async () => { fireEvent.click(resend); });
  expect(firebase.sendVerificationEmail).toHaveBeenCalledTimes(1); // cooldown blocks a second send
});

test('a password that leaves the email verified finishes without a verification email', async () => {
  firebase.linkPasswordCredential.mockImplementation(async (user) => {
    user.providerData = [...user.providerData, { providerId: 'password' }];
    return user; // emailVerified stays true
  });
  const { onLogin } = renderAt(state('INCOMPLETE', 'password', 'Lecturer'));
  await screen.findByRole('heading', { name: 'Set Your Password' });
  setPasswords('Strong#Pass1', 'Strong#Pass1');
  await waitFor(() => expect(onLogin).toHaveBeenCalled());
  expect(firebase.sendVerificationEmail).not.toHaveBeenCalled();
});

test('weak or mismatched passwords are blocked; "credential already in use" is explained', async () => {
  renderAt(state('INCOMPLETE', 'password', 'Lecturer'));
  await screen.findByRole('heading', { name: 'Set Your Password' });
  setPasswords('weakpass', 'weakpass');
  expect(await screen.findByText('Your password does not meet all the requirements.')).toBeInTheDocument();
  setPasswords('Strong#Pass1', 'Strong#Pass2');
  expect(await screen.findByText('Passwords do not match.')).toBeInTheDocument();
  expect(firebase.linkPasswordCredential).not.toHaveBeenCalled();

  firebase.linkPasswordCredential.mockRejectedValue(Object.assign(new Error('raw firebase text'), { code: 'auth/credential-already-in-use' }));
  setPasswords('Strong#Pass1', 'Strong#Pass1');
  expect(await screen.findByRole('alert')).toHaveTextContent('An email/password sign-in already exists for this email on another account');
  expect(screen.queryByText('raw firebase text')).not.toBeInTheDocument();
});

test('Test 12: no browser alerts anywhere in the flow', async () => {
  firebase.refreshEmailVerified.mockResolvedValue(false);
  renderAt(state('VERIFICATION_PENDING', 'verify', 'Lecturer'));
  fireEvent.click(await screen.findByRole('button', { name: "I've Verified" }));
  await screen.findByRole('alert');
  expect(window.alert).not.toHaveBeenCalled();
});
