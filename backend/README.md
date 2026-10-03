# Backend Authentication Setup (Firebase)

Sign-in uses **Firebase Authentication** with two methods on **one account per
email**:

```text
Firebase user (one uid)
 ├── Email/Password   (verified by email link)
 └── Google
```

Firebase holds the credentials. This backend verifies Firebase ID tokens with the
Firebase Admin SDK, keeps the app profile (full name, email, designation) in the
Firestore `users` collection, and issues its own session JWT. No passwords or
password hashes are stored here.

## How it works

| Flow | What happens |
|---|---|
| Register (`/register`) | `createUserWithEmailAndPassword` → `POST /api/auth/register-profile` saves full name + designation → `sendEmailVerification` → `/verify-email` |
| Verify (`/verify-email`) | Polls `reload()` every 5 s (plus a "Check Verification" button). When `emailVerified` is true: sign out of Firebase and redirect to `/login`. Never logs in automatically. |
| Password login | `signInWithEmailAndPassword` → unverified accounts go back to `/verify-email` → `POST /api/auth/firebase-login` returns the session JWT |
| Continue with Google | `signInWithPopup(GoogleAuthProvider)` → `POST /api/auth/firebase-login`. A first-time Google user gets a profile (designation defaults to "Researcher", editable on the Profile page). |
| Google for an existing password account | Firebase either links Google into the same uid automatically (Google is the trusted provider for the address), or returns `auth/account-exists-with-different-credential`. In that case the login form asks for the account password, signs in, then calls `linkWithCredential(googleCredential)`. Either way it is the same uid. |
| Password user who never used Google | The first "Continue with Google" with the same Gmail adds Google to that account, as in the row above. |
| Google-first user who wants a password | "Forgot Password?" on the login page. Completing Firebase's reset email sets a password on the same account. (Not exercised in testing; try it once on the real project.) |

### Security

* `verifyFirebaseToken` (`routes/auth.js`) verifies every ID token with the Admin
  SDK and reads `email_verified` from the **token**. A value such as
  `emailVerified: true` in the request body is ignored.
* A session JWT is only issued for tokens with `email_verified: true`. Google
  tokens always carry it, so Google users are not asked to verify again.
  Email/password users must click the verification link first; otherwise the
  backend returns `403 { code: "EMAIL_NOT_VERIFIED" }`.
* `/register-profile` accepts unverified tokens but only stores the profile. It
  never returns a session and never overwrites another account's profile.
* One profile per Firebase account. Profiles are found by Firebase uid, then by
  email, and new profiles use the uid as the Firestore document ID, so concurrent
  first logins cannot create duplicates.
* `PUT /api/auth/change-password` refuses Google-only accounts (they have no
  password to change).
* Only the public Firebase web config is in `frontend/.env`. The Admin SDK
  service account stays in `backend/` (`.env` / `serviceAccountKey.json`, both
  git-ignored).
* The legacy `POST /api/auth/register` (no verification, stored a password hash)
  returns `410 Gone`.

## 1. Firebase Console configuration

Do all of these in [Firebase Console](https://console.firebase.google.com) for the
project in `REACT_APP_FIREBASE_PROJECT_ID`.

1. **Authentication → Sign-in method → Email/Password**: Enable. Leave
   "Email link (passwordless sign-in)" off.
2. **Authentication → Sign-in method → Add new provider → Google**: Enable, choose
   a **project support email**, Save. Firebase creates the Google OAuth client for
   you. No Google Cloud OAuth setup is needed for the popup flow.
3. **Authentication → Settings → User account linking**: select **"Link accounts
   that use the same email"** (one account per email). This is what keeps
   email/password and Google on the same Firebase user. Do not choose "Create
   multiple accounts for each identity provider".
4. **Authentication → Settings → Authorized domains**: make sure `localhost` is
   listed, and add your deployed domain when you deploy. Both the Google popup and
   the verification-email redirect (`<origin>/login?verified=1`) require it.
5. **Authentication → Templates → Email address verification** (optional): set the
   sender name, subject and message.
6. **Google OAuth consent screen** (only if Google asks when you enable the
   provider, or you publish publicly): Google Cloud Console → APIs & Services →
   OAuth consent screen. Set the app name and support email, and add your domain.
7. **Firestore Database**: create it if it does not exist (profiles live in `users`).
8. **Project settings → Service accounts → Generate new private key**: the
   backend's Admin SDK key (see step 2 below).
9. **Project settings → General → Your apps → Web app**: copy the web config into
   `frontend/.env`.

## 2. Environment variables

`backend/.env` (see `.env.example`):

| Variable | Purpose |
|---|---|
| `FIREBASE_SERVICE_ACCOUNT_PATH` **or** `FIREBASE_SERVICE_ACCOUNT_BASE64` | Admin SDK credentials |
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | PostgreSQL (quote values containing `#`) |
| `JWT_SECRET`, `JWT_EXPIRES_IN`, `PORT` | Backend session tokens and port |

`frontend/.env` (see `frontend/.env.example`): `REACT_APP_API_URL` and the six
`REACT_APP_FIREBASE_*` web-config values. Restart `npm start` after editing.

No extra npm packages are needed: the frontend already has `firebase` (v12,
modular SDK) and the backend already has `firebase-admin`.

## 3. Run

```sh
cd backend && npm install && npm run dev      # http://localhost:5005
cd frontend && npm install && npm start       # http://localhost:3000
```

`http://localhost:5005/api/health` should report `"database": "connected"` and
`"firebaseAdmin": "configured"`.

## 4. Testing the flows

Use an inbox you control and a Google account with the **same Gmail address**.

1. **New email/password user**: `/register`, fill the form → `/verify-email` shows
   your address. Logging in now sends you back to `/verify-email`. Click the
   email link; the page detects it within about 5 s and goes to `/login`. Log in
   with the password → dashboard. Profile shows your full name and designation.
2. **Existing password user**: log out, log in with email + password → dashboard.
3. **Same account, Google too**: log out, "Continue with Google" with the same
   Gmail → dashboard with the same profile. Log out → the password still works.
   In Firebase Console → Authentication → Users there is still **one** row, now
   with both provider icons.
4. **Google-first user** (a Gmail not registered yet): "Continue with Google" →
   dashboard. Designation shows "Researcher" until edited on the Profile page.
5. **No duplicates**: registering an email that already has an account shows "An
   account already exists…". Repeated Google logins keep a single user in Firebase
   Console and a single document in Firestore `users`.

### Local testing without real accounts (Auth emulator)

The app can run against the Firebase Auth emulator (`firebase emulators:start
--only auth --project <project-id>`):

* frontend: `REACT_APP_FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099`
* backend: `FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099` and
  `FIREBASE_EMULATOR_PROJECT_ID=<project-id>`. Profiles are then kept in memory
  (add `FIRESTORE_EMULATOR_HOST` to use the Firestore emulator).

The emulator does not reproduce every production linking rule, so do one final
run of the steps above against the real project.

## 5. Feedback & issue reports (Cloud Firestore)

Signed-in users can **Send Feedback** or **Report an Issue** from the footer of any
page. Administrators manage both from **Admin** in the navbar.

| Collection | Fields | Default status | Allowed statuses |
|---|---|---|---|
| `feedback` | `userId`, `userEmail`, `feedbackType`, `message`, `status`, `createdAt`, `updatedAt` (+ `adminResponse`, set by admins) | `New` | `New`, `In Review`, `Resolved` |
| `issues` | `userId`, `userEmail`, `title`, `category`, `description`, `status`, `createdAt`, `updatedAt` (+ `adminResponse`) | `Open` | `Open`, `In Progress`, `Resolved`, `Closed` |

The browser writes these documents directly with the Firebase client SDK
(`frontend/src/services/supportService.js`). `firestore.rules` (repo root) decides
who may do what:

| | Create | Read | Change status / respond | Delete |
|---|---|---|---|---|
| Signed-out visitor | ✗ | ✗ | ✗ | ✗ |
| Signed-in user (verified email) | ✓ own only | ✓ own only | ✗ | ✗ |
| Admin (`admin` custom claim) | ✓ own only | ✓ all | ✓ status, `adminResponse` only | ✓ |

* On create, `userId` and `userEmail` must equal the signed-in user's uid and email
  from the verified ID token, the status must be the default, both timestamps must
  be the server time, and only the listed fields are accepted. Users therefore
  cannot post as someone else, back-date a submission or pre-resolve it.
* Admins can change only `status`, `adminResponse` and `updatedAt`. They cannot
  rewrite what the user submitted.
* Every other collection (`users`, `userLibraries`, …) is closed to browsers. The
  backend reaches it through the Admin SDK, which is not subject to these rules.

### Administrators

Admin access is the Firebase Auth custom claim `admin: true`. It is signed into the
user's ID token by Firebase, so it cannot be set from the browser, and the rules
check it on every request. Hiding the Admin link in React is only cosmetic.

```sh
cd backend
npm run set-admin -- someone@example.com            # grant
npm run set-admin -- someone@example.com --remove   # revoke
npm run set-admin -- --list                         # list admins
```

The person must log out and back in (or wait up to an hour) before the claim
appears in their token.

### Deploying the rules (required)

The rules live in `firestore.rules` and must be deployed to the Firebase project.
Until they are, the project's current rules apply, and submissions are usually
rejected.

```sh
firebase login
firebase deploy --only firestore:rules      # run from the repo root
```

`firebase.json` and `.firebaserc` (repo root) point the Firebase CLI at this project.
Firestore itself must already exist (Firebase Console → Firestore Database). No
composite indexes are needed.

### Attachments (not included)

Screenshot uploads are not implemented. Adding them needs:

1. **Cloud Storage** enabled for the project. New default buckets now require the
   Blaze (pay-as-you-go) plan.
2. `storage.rules` that only let a signed-in user write under their own folder,
   `feedback/{uid}/…` or `issues/{uid}/…`, limit the size (for example 5 MB) and
   allow only `image/*`. Only admins and the owner may read.
3. In the modals, upload with `uploadBytes`, then save the file's storage *path*
   (not the image) as `attachmentPath` on the document, and allow that one extra
   field in `firestore.rules`.

### Testing locally with the emulators

```sh
firebase emulators:start --only auth,firestore      # repo root; uses firebase.json
```

* frontend: `REACT_APP_FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099` and
  `REACT_APP_FIRESTORE_EMULATOR_HOST=127.0.0.1:8085`
* backend: `FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099`,
  `FIRESTORE_EMULATOR_HOST=127.0.0.1:8085`, `FIREBASE_EMULATOR_PROJECT_ID=<project-id>`

Then:

1. Log in and use **Send Feedback** and **Report an Issue** in the footer. Each
   shows a success message, and the document appears in the emulator.
2. Make yourself admin (`npm run set-admin` with the emulator variables above),
   log out and back in. **Admin** appears in the navbar and lists every
   submission. Changing a status saves it.
3. Log in as a second, non-admin user. The Admin link is hidden, and reading another
   user's document from the browser console fails with `permission-denied`.
