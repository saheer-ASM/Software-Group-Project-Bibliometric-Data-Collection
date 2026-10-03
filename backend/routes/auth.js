const express = require('express');
const jwt = require('jsonwebtoken');
const admin = require('firebase-admin');
const authMiddleware = require('../middleware/auth');
const userStore = require('../services/firebaseUserStore');
const JWT_SECRET = process.env.JWT_SECRET || 'dev-secret';

const router = express.Router();

function signToken(id) {
  return jwt.sign({ id }, JWT_SECRET, {
    expiresIn: process.env.JWT_EXPIRES_IN || '7d',
  });
}

function httpError(status, message, code) {
  const err = new Error(message);
  err.status = status;
  if (code) err.code = code;
  return err;
}

function sendError(res, err, fallbackMessage) {
  if (err.status) {
    return res.status(err.status).json({ message: err.message, ...(err.code ? { code: err.code } : {}) });
  }
  return res.status(401).json({ message: fallbackMessage, error: err.message });
}

// Verifies a Firebase ID token with the Admin SDK (signature, expiry, audience).
// Whether the email is verified comes from the token's own `email_verified`
// claim, never from a value the client sends in the request body.
// Email/password accounts must be verified; federated providers (Google, GitHub)
// are unchanged, since their email is vouched for by the provider.
async function verifyFirebaseToken(idToken, { requireVerifiedEmail = true } = {}) {
  if (!idToken) throw httpError(400, 'Firebase token is required');
  if (!admin.apps.length) throw httpError(503, 'Firebase admin is not configured on the backend');

  const decoded = await admin.auth().verifyIdToken(idToken);
  if (!decoded.email) throw httpError(400, 'No email in token');

  // Google sign-ins always carry email_verified: true (Google owns the address),
  // so they pass straight through; email/password accounts pass only after the
  // verification link has been clicked.
  if (requireVerifiedEmail && decoded.email_verified !== true) {
    throw httpError(403, 'Please verify your email address before signing in.', 'EMAIL_NOT_VERIFIED');
  }
  return decoded;
}

// One profile per Firebase account. Firebase links Google and email/password
// for the same email into ONE uid, so look the profile up by uid first, then by
// email (accounts created before uids were stored). Never creates a profile.
async function findProfile(decoded) {
  let user = await userStore.findByFirebaseUid(decoded.uid);
  if (!user) user = await userStore.findByEmail(decoded.email);
  if (!user) return null;

  const updates = {};
  // The token proves ownership of this verified email, so it is safe to point
  // the profile at the current Firebase uid.
  if (user.firebaseUid !== decoded.uid) updates.firebaseUid = decoded.uid;
  // Keep the stored email equal to the verified Firebase email (repairs profiles
  // edited before the email became read-only).
  if (user.email !== decoded.email.toLowerCase()) updates.email = decoded.email;
  if (user.emailVerified !== (decoded.email_verified === true)) {
    updates.emailVerified = decoded.email_verified === true;
  }
  return Object.keys(updates).length ? userStore.updateUser(user.id, updates) : user;
}

// Only the Register page starts a ScholarMetrics registration: a first Google
// sign-in there creates an INCOMPLETE profile (designation + password + email
// verification still to do). Sign In never creates profiles.
function createIncompleteProfile(decoded) {
  return userStore.createFirebaseUser({
    username: decoded.name || decoded.email.split('@')[0] || 'User',
    email: decoded.email,
    designation: '',
    firebaseUid: decoded.uid,
    emailVerified: decoded.email_verified === true,
    profileCompleted: false,
  });
}

// A Sign In pop-up creates a Firebase Auth record for any Google account. If that
// account never registered (no profile, Google-only), remove the record again.
// Email/password records are never touched.
async function removeUnregisteredGoogleUser(uid) {
  try {
    const firebaseUser = await admin.auth().getUser(uid);
    const providers = firebaseUser.providerData.map((p) => p.providerId);
    if (!providers.includes('password')) await admin.auth().deleteUser(uid);
  } catch (err) {
    console.warn('Could not remove unregistered Firebase user:', err.message);
  }
}

const isProfileComplete = (user) => user.profileCompleted !== false;

const profileSummary = (user) => ({ username: user.username, email: user.email, designation: user.designation || '' });

// Registration state = the stored "completed" flag (profileCompleted) plus facts
// read from Firebase itself, so the remaining step can never be out of date:
//   no designation             -> step 'profile'   (INCOMPLETE)
//   no email/password sign-in  -> step 'password'  (INCOMPLETE)
//   email not verified         -> step 'verify'    (VERIFICATION_PENDING)
//   all done                   -> COMPLETED (flag is set here)
// Verification is Firebase's own emailVerified on the user record, never a
// value sent by the browser.
async function registrationState(user, uid) {
  const firebaseUser = await admin.auth().getUser(uid);
  const hasPassword = firebaseUser.providerData.some((p) => p.providerId === 'password');
  const verified = firebaseUser.emailVerified === true;

  if (isProfileComplete(user)) {
    // Finished profiles still need a verified email to sign in (existing rule).
    return { user, status: verified ? 'COMPLETED' : 'COMPLETED_UNVERIFIED' };
  }
  let step = null;
  if (!user.designation) step = 'profile';
  else if (!hasPassword) step = 'password';
  else if (!verified) step = 'verify';

  if (!step) {
    const completed = await userStore.updateUser(user.id, { profileCompleted: true, emailVerified: true });
    return { user: completed, status: 'COMPLETED' };
  }
  return { user, status: step === 'verify' ? 'VERIFICATION_PENDING' : 'INCOMPLETE', step };
}

// Response for a registration state. Only COMPLETED gets the session JWT.
function sendState(res, { user, status, step }) {
  if (status === 'COMPLETED') {
    return res.json({ status, profileCompleted: true, token: signToken(user.id), user: userStore.publicUser(user) });
  }
  if (status === 'COMPLETED_UNVERIFIED') {
    return res.json({ status, code: 'EMAIL_NOT_VERIFIED', email: user.email });
  }
  return res.json({ status, step, profileCompleted: false, profile: profileSummary(user) });
}

// Routes that start a session for a token whose email is already verified
// (verifyFirebaseToken checked it). Incomplete profiles get no token.
function sendSession(res, user) {
  if (!isProfileComplete(user)) {
    return res.json({ status: 'INCOMPLETE', profileCompleted: false, profile: profileSummary(user) });
  }
  return res.json({ status: 'COMPLETED', profileCompleted: true, token: signToken(user.id), user: userStore.publicUser(user) });
}

const notRegistered = (res) => res.status(404).json({
  status: 'NOT_REGISTERED',
  code: 'ACCOUNT_NOT_FOUND',
  message: 'No ScholarMetrics account found. Please create an account first.',
});

// POST /api/auth/register-profile
// Called right after the frontend creates the Firebase email/password account.
// Saves Full Name + Designation for the new (still unverified) account. It does
// NOT issue a session token; that only happens in /firebase-login once the
// email is verified.
router.post('/register-profile', async (req, res) => {
  try {
    const { idToken, username, designation } = req.body;
    const decoded = await verifyFirebaseToken(idToken, { requireVerifiedEmail: false });

    if (decoded.firebase?.sign_in_provider !== 'password') {
      return res.status(400).json({ message: 'Only email/password registrations use this endpoint' });
    }
    if (!username?.trim() || !designation?.trim()) {
      return res.status(400).json({ message: 'Full name and designation are required' });
    }
    if (username.trim().length > 100 || designation.trim().length > 100) {
      return res.status(400).json({ message: 'Full name and designation must be at most 100 characters' });
    }

    const existing = await userStore.findByEmail(decoded.email);
    if (existing && existing.firebaseUid !== decoded.uid) {
      // Never let a new, unverified account overwrite somebody else's profile.
      return res.status(409).json({ message: 'An account already exists with this email address.' });
    }

    if (existing) {
      await userStore.updateUser(existing.id, { username, designation });
    } else {
      await userStore.createFirebaseUser({
        username,
        email: decoded.email,
        designation,
        firebaseUid: decoded.uid,
        emailVerified: decoded.email_verified === true,
      });
    }

    res.status(201).json({ message: 'Profile saved. Please verify your email address.' });
  } catch (err) {
    sendError(res, err, 'Could not save registration');
  }
});

// POST /api/auth/firebase-login
// Exchanges a verified Firebase ID token (email/password OR Google, same
// Firebase account) for this backend's session JWT.
router.post('/firebase-login', async (req, res) => {
  try {
    const { idToken, username: requestedUsername, designation: requestedDesignation } = req.body;
    const decoded = await verifyFirebaseToken(idToken);

    let user = await findProfile(decoded);
    if (!user) return notRegistered(res);

    // Name/designation edits here only apply to completed profiles; incomplete
    // ones are finished through the registration routes.
    const updates = {};
    if (requestedUsername?.trim()) updates.username = requestedUsername;
    if (requestedDesignation?.trim()) updates.designation = requestedDesignation;
    if (isProfileComplete(user) && Object.keys(updates).length) {
      user = await userStore.updateUser(user.id, updates);
    }

    sendSession(res, user);
  } catch (err) {
    sendError(res, err, 'Sign-in failed');
  }
});

// POST /api/auth/registration-status  { idToken, intent: 'register' | 'signin' }
// Decides what a (Google or password) sign-in means for ScholarMetrics:
//   NOT_REGISTERED        no profile (Sign In only; the Register page creates one)
//   INCOMPLETE            + step 'profile' | 'password'
//   VERIFICATION_PENDING  + step 'verify'
//   COMPLETED_UNVERIFIED  finished profile, email not verified yet
//   COMPLETED             + session token
// Accepts unverified tokens on purpose: it is how unfinished registrations are
// recognised. It never issues a session unless Firebase reports a verified email.
router.post('/registration-status', async (req, res) => {
  try {
    const decoded = await verifyFirebaseToken(req.body.idToken, { requireVerifiedEmail: false });
    const intent = req.body.intent === 'register' ? 'register' : 'signin';

    let user = await findProfile(decoded);
    if (!user) {
      if (intent !== 'register') {
        await removeUnregisteredGoogleUser(decoded.uid);
        return notRegistered(res);
      }
      user = await createIncompleteProfile(decoded);
    }
    sendState(res, await registrationState(user, decoded.uid));
  } catch (err) {
    sendError(res, err, 'Could not check your account');
  }
});

// POST /api/auth/registration/profile  { idToken, username, designation }
// Saves step 1 (Complete Your Profile) of an unfinished registration, so a user
// who leaves later resumes at the next step.
router.post('/registration/profile', async (req, res) => {
  try {
    const decoded = await verifyFirebaseToken(req.body.idToken, { requireVerifiedEmail: false });
    const username = String(req.body.username || '').trim();
    const designation = String(req.body.designation || '').trim();

    if (username.length < 3 || username.length > 100) {
      return res.status(400).json({ message: 'Full name must be between 3 and 100 characters.' });
    }
    if (designation.length < 2 || designation.length > 100) {
      return res.status(400).json({ message: 'Designation must be between 2 and 100 characters.' });
    }

    let user = await findProfile(decoded);
    if (!user) return notRegistered(res);
    if (isProfileComplete(user)) {
      // Finished profiles are edited on the Settings page, not here.
      return res.status(409).json({ message: 'Your registration is already complete.' });
    }
    user = await userStore.updateUser(user.id, { username, designation });
    sendState(res, await registrationState(user, decoded.uid));
  } catch (err) {
    sendError(res, err, 'Could not save your profile');
  }
});

// POST /api/auth/complete-profile  { idToken }
// Final step: "I've Verified". The token itself must carry email_verified: true
// (verifyFirebaseToken), and the profile must have a designation and a linked
// email/password sign-in. Then the profile is marked complete and the session
// is issued.
router.post('/complete-profile', async (req, res) => {
  try {
    const decoded = await verifyFirebaseToken(req.body.idToken);
    const user = await findProfile(decoded);
    if (!user) return notRegistered(res);

    const state = await registrationState(user, decoded.uid);
    if (state.status !== 'COMPLETED') {
      return res.status(400).json({
        status: state.status,
        step: state.step,
        code: state.step === 'password' ? 'PASSWORD_REQUIRED' : 'REGISTRATION_INCOMPLETE',
        message: 'Please finish the remaining registration steps.',
      });
    }
    sendState(res, state);
  } catch (err) {
    sendError(res, err, 'Could not complete your registration');
  }
});

// POST /api/auth/register  (legacy, disabled)
// It created accounts and issued a session with no email verification, and
// stored a password hash. Registration now goes through Firebase Authentication:
// /register-profile, then email verification, then /firebase-login.
router.post('/register', (_req, res) => {
  res.status(410).json({
    message: 'This registration endpoint is no longer available. Please register through the website.',
  });
});

// POST /api/auth/login
router.post('/login', async (req, res) => {
  try {
    const { username, password } = req.body;

    if (!username || !password) {
      return res.status(400).json({ message: 'Username and password are required' });
    }

    const user = await userStore.findByUsername(username);
    if (!user || !(await userStore.comparePassword(user, password))) {
      return res.status(401).json({ message: 'Invalid username or password' });
    }
    if (user.firebaseUid && admin.apps.length) {
      const firebaseUser = await admin.auth().getUser(user.firebaseUid).catch(() => null);
      const isPasswordAccount = firebaseUser?.providerData.some((p) => p.providerId === 'password');
      if (isPasswordAccount && !firebaseUser.emailVerified) {
        return res.status(403).json({
          message: 'Please verify your email address before signing in.',
          code: 'EMAIL_NOT_VERIFIED',
        });
      }
    }

    sendSession(res, user);
  } catch (err) {
    res.status(500).json({ message: 'Server error', error: err.message });
  }
});

// POST /api/auth/social  (Google / GitHub sign-in)
router.post('/social', async (req, res) => {
  try {
    const decoded = await verifyFirebaseToken(req.body.idToken);
    const user = await findProfile(decoded);
    if (!user) return notRegistered(res);
    sendSession(res, user);
  } catch (err) {
    sendError(res, err, 'Social sign-in failed');
  }
});

// POST /api/auth/reset-password
// Called after the user completes Firebase's "forgot password" email flow
// (confirmPasswordReset + sign-in on the frontend). Firebase already holds the
// new password, so this only clears any legacy password hash and starts a session.
router.post('/reset-password', async (req, res) => {
  try {
    const decoded = await verifyFirebaseToken(req.body.idToken);

    const user = await userStore.findByEmail(decoded.email);
    if (!user) return res.status(404).json({ message: 'No account found for this email' });

    if (user.password) await userStore.updateUser(user.id, { password: null });

    sendSession(res, user);
  } catch (err) {
    sendError(res, err, 'Password reset failed');
  }
});

// GET /api/auth/profile  (protected)
router.get('/profile', authMiddleware, (req, res) => {
  res.json(userStore.publicUser(req.user));
});

// PUT /api/auth/profile  (protected)
router.put('/profile', authMiddleware, async (req, res) => {
  try {
    const { username, email, designation } = req.body;

    // The registered email is the account's identity (it comes from the verified
    // Firebase account) and cannot be changed through the profile.
    if (email !== undefined && String(email).trim().toLowerCase() !== req.user.email) {
      return res.status(400).json({ message: 'Your registered email address cannot be changed.' });
    }

    const updates = {};
    if (username) updates.username = username;
    if (designation) updates.designation = designation;

    if (updates.username && updates.username.trim().length < 3) {
      return res.status(400).json({ message: 'Username must be at least 3 characters' });
    }

    if (updates.username) {
      const conflict = await userStore.findConflict({
        username: updates.username,
        excludeId: req.user.id,
      });
      if (conflict) {
        return res.status(409).json({ message: 'Username already taken' });
      }
    }

    const updated = await userStore.updateUser(req.user.id, updates);

    res.json(userStore.publicUser(updated));
  } catch (err) {
    res.status(500).json({ message: 'Server error', error: err.message });
  }
});

// PUT /api/auth/change-password  (retired)
// It set a new password with Admin rights after only an email match, so a
// stolen session token was enough to change the password. Password changes
// now happen in the browser through Firebase (re-authenticate with the current
// password, then updatePassword), where Firebase itself checks the current
// password.
router.put('/change-password', authMiddleware, (_req, res) => {
  res.status(410).json({
    message: 'Password changes are now made from the Profile page using your current password.',
  });
});

module.exports = router;
