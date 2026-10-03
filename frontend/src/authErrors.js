// Maps Firebase Auth error codes (and this backend's own codes) to messages a
// user can act on. Unknown codes fall back to the supplied default, never to the
// raw Firebase code.
const MESSAGES = {
  'auth/email-already-in-use':
    'An account already exists with this email. Log in instead, or use "Continue with Google" if you signed up with Google.',
  'auth/invalid-email': 'Please enter a valid email address.',
  'auth/missing-email': 'Please enter your email address.',
  'auth/weak-password': 'That password is too weak. Please meet all the password requirements.',
  'auth/password-does-not-meet-requirements': 'That password does not meet the password requirements.',
  'auth/missing-password': 'Please enter your password.',
  'auth/wrong-password': 'Incorrect password. Please try again.',
  'auth/user-not-found': 'No account was found with this email address.',
  // Firebase returns this single code for wrong password AND unknown email when
  // email-enumeration protection is on, so the message covers both.
  'auth/invalid-credential':
    'Invalid email or password. If you signed up with Google, use "Continue with Google".',
  'auth/invalid-login-credentials':
    'Invalid email or password. If you signed up with Google, use "Continue with Google".',
  'auth/user-disabled': 'This account has been disabled. Please contact support.',
  'auth/popup-closed-by-user': 'The Google sign-in window was closed before finishing.',
  'auth/cancelled-popup-request': 'The Google sign-in window was closed before finishing.',
  'auth/popup-blocked': 'The sign-in popup was blocked by the browser. Allow popups for this site and try again.',
  'auth/account-exists-with-different-credential':
    'An account already exists with this email using a different sign-in method.',
  'auth/credential-already-in-use':
    'This Google account is already connected to a different account.',
  'auth/email-change-needs-verification': 'Please verify your email address first.',
  'auth/provider-already-linked': 'This sign-in method is already linked to your account.',
  'auth/requires-recent-login': 'For your security, please sign in again and retry.',
  'auth/network-request-failed': 'Network error. Check your internet connection and try again.',
  'auth/too-many-requests': 'Too many attempts. Please wait a few minutes and try again.',
  'auth/operation-not-allowed':
    'This sign-in method is not enabled for this app yet. Please contact the administrator.',
  'auth/unauthorized-domain':
    'This website is not authorised for sign-in. Add it under Firebase Authentication > Settings > Authorized domains.',
  'auth/user-token-expired': 'Your session has expired. Please log in again.',
  'auth/expired-action-code': 'This link has expired. Please request a new one.',
  'auth/invalid-action-code': 'This link is invalid or has already been used.',
  EMAIL_NOT_VERIFIED: 'Please verify your email address before logging in.',
};

export const authErrorMessage = (err, fallback = 'Something went wrong. Please try again.') =>
  MESSAGES[err?.code] || fallback;
