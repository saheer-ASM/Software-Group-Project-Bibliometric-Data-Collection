# Backend Firebase Setup

The authentication routes store users in Firebase Firestore. User passwords are hashed before they are saved.

## 1. Create Firebase credentials

1. Open Firebase Console.
2. Create or select a project.
3. Go to Project settings > Service accounts.
4. Click Generate new private key and download the JSON file.
5. Enable Firestore Database for the project.

## 2. Configure `.env`

Copy `.env.example` to `.env`, then add the service account JSON as base64:

```sh
base64 -i serviceAccountKey.json
```

Put the output into:

```env
FIREBASE_SERVICE_ACCOUNT_BASE64=your_base64_encoded_service_account_json
JWT_SECRET=your_long_random_secret
JWT_EXPIRES_IN=7d
PORT=5001
```

## 3. Run the backend

```sh
npm install
npm run dev
```

New signups are saved in the Firestore `users` collection.
