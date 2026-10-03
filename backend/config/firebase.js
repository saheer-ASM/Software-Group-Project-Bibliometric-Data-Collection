const admin = require('firebase-admin');
const fs = require('fs');
const path = require('path');

function getServiceAccount() {
  // Try base64-encoded credentials first (best for production)
  if (process.env.FIREBASE_SERVICE_ACCOUNT_BASE64) {
    const decoded = Buffer.from(process.env.FIREBASE_SERVICE_ACCOUNT_BASE64, 'base64').toString('utf8');
    return JSON.parse(decoded);
  }

  // Try JSON string in env var
  if (process.env.FIREBASE_SERVICE_ACCOUNT_JSON) {
    return JSON.parse(process.env.FIREBASE_SERVICE_ACCOUNT_JSON);
  }

  // Try path from env var
  if (process.env.FIREBASE_SERVICE_ACCOUNT_PATH) {
    try {
      const configuredPath = process.env.FIREBASE_SERVICE_ACCOUNT_PATH;
      const serviceAccountPath = path.isAbsolute(configuredPath)
        ? configuredPath
        : path.resolve(__dirname, '..', configuredPath);
      if (fs.existsSync(serviceAccountPath)) {
        return JSON.parse(fs.readFileSync(serviceAccountPath, 'utf8'));
      }
    } catch (err) {
      console.warn(`Could not load Firebase credentials from path:`, err.message);
    }
  }

  // Try individual environment variables
  if (
    process.env.FIREBASE_PROJECT_ID &&
    process.env.FIREBASE_CLIENT_EMAIL &&
    process.env.FIREBASE_PRIVATE_KEY
  ) {
    return {
      project_id: process.env.FIREBASE_PROJECT_ID,
      client_email: process.env.FIREBASE_CLIENT_EMAIL,
      private_key: process.env.FIREBASE_PRIVATE_KEY.replace(/\\n/g, '\n'),
    };
  }

  return null;
}

// Local testing against the Firebase Auth emulator
// (FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099 + FIREBASE_EMULATOR_PROJECT_ID).
// No credentials are used, and profiles go to the in-memory user store unless
// FIRESTORE_EMULATOR_HOST is also set. Unset in normal use.
const emulatorProjectId = process.env.FIREBASE_AUTH_EMULATOR_HOST && process.env.FIREBASE_EMULATOR_PROJECT_ID;

const serviceAccount = emulatorProjectId ? null : getServiceAccount();

if (serviceAccount && !admin.apps.length) {
  admin.initializeApp({
    credential: admin.credential.cert(serviceAccount),
    ...(process.env.FIREBASE_DATABASE_URL
      ? { databaseURL: process.env.FIREBASE_DATABASE_URL }
      : {}),
  });
} else if (emulatorProjectId && !admin.apps.length) {
  admin.initializeApp({ projectId: emulatorProjectId });
}

const useFirestore = serviceAccount || (emulatorProjectId && process.env.FIRESTORE_EMULATOR_HOST);
module.exports = useFirestore ? admin.firestore() : null;
