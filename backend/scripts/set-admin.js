// Grants or removes the ScholarMetrics administrator role.
//
//   npm run set-admin -- user@example.com            grant
//   npm run set-admin -- user@example.com --remove   remove
//   npm run set-admin -- --list                      show current admins
//
// The role is the Firebase Auth custom claim `admin: true`. Claims are signed
// into the user's ID token by Firebase, so they cannot be set from a browser,
// and the Firestore Security Rules (firestore.rules) check this claim before
// allowing anyone to read or manage feedback and issues.
//
// The user must log out and back in afterwards (or wait up to an hour) for the
// new claim to appear in their token.
require('dotenv').config({ path: require('path').resolve(__dirname, '..', '.env') });
require('../config/firebase');
const admin = require('firebase-admin');

async function listAdmins() {
  let pageToken;
  const admins = [];
  do {
    const page = await admin.auth().listUsers(1000, pageToken);
    admins.push(...page.users.filter((u) => u.customClaims?.admin === true).map((u) => u.email));
    pageToken = page.pageToken;
  } while (pageToken);
  console.log(admins.length ? `Admins:\n  ${admins.join('\n  ')}` : 'No admins set.');
}

async function main() {
  if (!admin.apps.length) {
    throw new Error('Firebase Admin is not configured. Check FIREBASE_SERVICE_ACCOUNT_* in backend/.env.');
  }

  const args = process.argv.slice(2);
  if (args.includes('--list')) return listAdmins();

  const email = args.find((a) => !a.startsWith('--'));
  const remove = args.includes('--remove');
  if (!email) {
    console.log('Usage: npm run set-admin -- <email> [--remove] | --list');
    process.exitCode = 1;
    return;
  }

  const user = await admin.auth().getUserByEmail(email.trim().toLowerCase());
  const claims = { ...(user.customClaims || {}) };
  if (remove) delete claims.admin;
  else claims.admin = true;

  await admin.auth().setCustomUserClaims(user.uid, claims);
  console.log(`${remove ? 'Removed admin role from' : 'Granted admin role to'} ${user.email} (uid ${user.uid}).`);
  console.log('They must log out and log in again for the change to take effect.');
}

main().catch((err) => {
  console.error(`Error: ${err.message}`);
  process.exitCode = 1;
});
