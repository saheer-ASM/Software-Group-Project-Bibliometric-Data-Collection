import { initializeApp } from 'firebase/app';
import {
  getAuth,
  connectAuthEmulator,
  createUserWithEmailAndPassword,
  sendEmailVerification,
  reload,
  GoogleAuthProvider,
  EmailAuthProvider,
  signInWithPopup,
  signInWithEmailAndPassword,
  reauthenticateWithCredential,
  updatePassword,
} from 'firebase/auth';
import { getFirestore, connectFirestoreEmulator } from 'firebase/firestore';

// All values come from frontend/.env (REACT_APP_FIREBASE_*); nothing is hard-coded.
// These are the public web-app identifiers only. The Admin SDK service account
// stays on the backend.
const firebaseConfig = {
  apiKey: process.env.REACT_APP_FIREBASE_API_KEY,
  authDomain: process.env.REACT_APP_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.REACT_APP_FIREBASE_PROJECT_ID,
  storageBucket: process.env.REACT_APP_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.REACT_APP_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.REACT_APP_FIREBASE_APP_ID,
};

const requiredConfig = ['apiKey', 'authDomain', 'projectId', 'appId'];
const missingConfig = requiredConfig.filter((key) => !firebaseConfig[key]);

const app = missingConfig.length === 0 ? initializeApp(firebaseConfig) : null;
const auth = app ? getAuth(app) : null;
const firestore = app ? getFirestore(app) : null;

// Optional: point at the local Firebase Auth emulator for testing
// (REACT_APP_FIREBASE_AUTH_EMULATOR_HOST=localhost:9099). Unset in normal use.
if (auth && process.env.REACT_APP_FIREBASE_AUTH_EMULATOR_HOST) {
  connectAuthEmulator(auth, `http://${process.env.REACT_APP_FIREBASE_AUTH_EMULATOR_HOST}`, {
    disableWarnings: true,
  });
}
// Optional: local Firestore emulator (REACT_APP_FIRESTORE_EMULATOR_HOST=127.0.0.1:8085).
if (firestore && process.env.REACT_APP_FIRESTORE_EMULATOR_HOST) {
  const [host, port] = process.env.REACT_APP_FIRESTORE_EMULATOR_HOST.split(':');
  connectFirestoreEmulator(firestore, host, Number(port));
}

// True only when the signed-in user's ID token carries the `admin` custom claim
// (granted with `npm run set-admin` in backend/). This only decides whether to
// SHOW admin pages; Firestore Security Rules enforce the same claim server-side.
const hasAdminClaim = async (user) => {
  if (!user) return false;
  const { claims } = await user.getIdTokenResult();
  return claims.admin === true;
};

const googleProvider = () => {
  const provider = new GoogleAuthProvider();
  provider.setCustomParameters({ prompt: 'select_account' });
  return provider;
};

// Where the link in the verification email sends the user after Firebase marks
// the address as verified. The domain must be listed under
// Firebase Console > Authentication > Settings > Authorized domains.
const verificationActionSettings = () => ({
  url: `${window.location.origin}/login?verified=1`,
});

const registerWithEmail = (email, password) => createUserWithEmailAndPassword(auth, email, password);

const sendVerificationEmail = (user) => sendEmailVerification(user, verificationActionSettings());

// Re-fetches the user record from Firebase so `emailVerified` reflects the
// latest state, then forces a new ID token so its `email_verified` claim
// (the value the backend trusts) is up to date as well.
const refreshEmailVerified = async (user) => {
  await reload(user);
  if (user.emailVerified) await user.getIdToken(true);
  return user.emailVerified;
};

const signInWithGoogle = () => signInWithPopup(auth, googleProvider());

// Credential Firebase returns with auth/account-exists-with-different-credential,
// so it can be linked once the user proves they own the existing account.
const googleCredentialFromError = (err) => GoogleAuthProvider.credentialFromError(err);

// Changes the password of an email/password account. Firebase checks the
// current password (re-authentication) before allowing the update, so a stolen
// session alone cannot change it. If the Firebase session has expired, signing
// in with the current password does the same check.
const changeAccountPassword = async (email, currentPassword, newPassword) => {
  let user = auth.currentUser;
  if (user) {
    if (!user.providerData.some((p) => p.providerId === EmailAuthProvider.PROVIDER_ID)) {
      const err = new Error('This account has no password.');
      err.code = 'app/no-password-provider';
      throw err;
    }
    await reauthenticateWithCredential(user, EmailAuthProvider.credential(user.email, currentPassword));
  } else {
    user = (await signInWithEmailAndPassword(auth, email, currentPassword)).user;
  }
  await updatePassword(user, newPassword);
};

export {
  auth,
  firestore,
  hasAdminClaim,
  missingConfig,
  registerWithEmail,
  sendVerificationEmail,
  refreshEmailVerified,
  signInWithGoogle,
  googleCredentialFromError,
  changeAccountPassword,
};
