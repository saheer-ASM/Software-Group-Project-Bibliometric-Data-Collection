// ScholarMetrics registration state for a signed-in Firebase user. The backend
// decides the state from its profile store plus Firebase's own records
// (password linked? email verified?), so nothing here is trusted on its own.
//
// status: 'NOT_REGISTERED' | 'INCOMPLETE' | 'VERIFICATION_PENDING'
//       | 'COMPLETED_UNVERIFIED' | 'COMPLETED' (with token + user)
// step (unfinished registrations): 'profile' | 'password' | 'verify'
import { API_BASE_URL } from '../config/api';

const post = async (path, body) => {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  // NOT_REGISTERED comes back as 404 but is a normal answer, not an error.
  if (!res.ok && data.status !== 'NOT_REGISTERED') {
    const err = new Error(data.message || 'Request failed');
    err.code = data.code;
    err.step = data.step;
    throw err;
  }
  return data;
};

// intent 'register' (Register page) may start a registration; 'signin' never does.
export const getRegistrationState = async (firebaseUser, intent) =>
  post('/api/auth/registration-status', { idToken: await firebaseUser.getIdToken(), intent });

export const saveRegistrationProfile = async (firebaseUser, { username, designation }) =>
  post('/api/auth/registration/profile', { idToken: await firebaseUser.getIdToken(), username, designation });

// Needs a FRESH token so its email_verified claim reflects the verification.
export const completeRegistration = async (firebaseUser) =>
  post('/api/auth/complete-profile', { idToken: await firebaseUser.getIdToken(true) });

// Seconds between "Resend Verification Email" clicks (Firebase also rate-limits).
export const RESEND_COOLDOWN_S = 60;
