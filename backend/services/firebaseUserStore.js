const bcrypt = require('bcryptjs');
const admin = require('firebase-admin');
const db = require('../config/firebase');

const usersCollection = db.collection('users');

function normalizeEmail(email) {
  return email.trim().toLowerCase();
}

function normalizeUsername(username) {
  return username.trim();
}

function userFromDoc(doc) {
  if (!doc.exists) return null;
  const data = doc.data();

  return {
    id: doc.id,
    username: data.username,
    usernameLower: data.usernameLower,
    email: data.email,
    designation: data.designation,
    password: data.password,
    firebaseUid: data.firebaseUid,
    createdAt: data.createdAt,
    updatedAt: data.updatedAt,
  };
}

function publicUser(user) {
  return {
    id: user.id,
    username: user.username,
    email: user.email,
    designation: user.designation,
  };
}

async function findById(id) {
  const doc = await usersCollection.doc(id).get();
  return userFromDoc(doc);
}

async function findByUsername(username) {
  const snapshot = await usersCollection
    .where('usernameLower', '==', normalizeUsername(username).toLowerCase())
    .limit(1)
    .get();

  if (snapshot.empty) return null;
  return userFromDoc(snapshot.docs[0]);
}

async function findByEmail(email) {
  const snapshot = await usersCollection.where('email', '==', normalizeEmail(email)).limit(1).get();

  if (snapshot.empty) return null;
  return userFromDoc(snapshot.docs[0]);
}

async function findConflict({ username, email, excludeId }) {
  const [usernameMatch, emailMatch] = await Promise.all([
    username ? findByUsername(username) : null,
    email ? findByEmail(email) : null,
  ]);

  return [usernameMatch, emailMatch].find((user) => user && user.id !== excludeId) || null;
}

async function ensureFirebaseAuthUser({ email, password, displayName }) {
  try {
    const created = await admin.auth().createUser({ email, password, displayName });
    return created.uid;
  } catch (err) {
    if (err.code === 'auth/email-already-exists') {
      // Account already exists (e.g. created earlier via social sign-in) — align its password
      // so Firebase's "forgot password" email flow keeps working for this user.
      const existing = await admin.auth().getUserByEmail(email);
      await admin.auth().updateUser(existing.uid, { password });
      return existing.uid;
    }
    console.warn('Could not create Firebase Auth user:', err.message);
    return null;
  }
}

async function createUser({ username, email, designation, password }) {
  const now = new Date().toISOString();
  const normalizedEmail = normalizeEmail(email);
  const hashedPassword = await bcrypt.hash(password, 12);
  const firebaseUid = await ensureFirebaseAuthUser({
    email: normalizedEmail,
    password,
    displayName: normalizeUsername(username),
  });
  const docRef = usersCollection.doc();
  const user = {
    username: normalizeUsername(username),
    usernameLower: normalizeUsername(username).toLowerCase(),
    email: normalizedEmail,
    designation: designation.trim(),
    password: hashedPassword,
    firebaseUid,
    createdAt: now,
    updatedAt: now,
  };

  await docRef.set(user);
  return { id: docRef.id, ...user };
}

async function updateUser(id, updates) {
  const cleanUpdates = {
    ...updates,
    updatedAt: new Date().toISOString(),
  };

  if (cleanUpdates.username) {
    cleanUpdates.username = normalizeUsername(cleanUpdates.username);
    cleanUpdates.usernameLower = cleanUpdates.username.toLowerCase();
  }

  if (cleanUpdates.email) {
    cleanUpdates.email = normalizeEmail(cleanUpdates.email);
  }

  if (cleanUpdates.designation) {
    cleanUpdates.designation = cleanUpdates.designation.trim();
  }

  await usersCollection.doc(id).update(cleanUpdates);
  return findById(id);
}

async function updatePassword(id, newPassword, { syncFirebase = true } = {}) {
  const hashedPassword = await bcrypt.hash(newPassword, 12);
  await usersCollection.doc(id).update({
    password: hashedPassword,
    updatedAt: new Date().toISOString(),
  });

  if (syncFirebase) {
    const user = await findById(id);
    if (user.firebaseUid) {
      try {
        await admin.auth().updateUser(user.firebaseUid, { password: newPassword });
      } catch (err) {
        console.warn('Could not sync password to Firebase Auth:', err.message);
      }
    }
  }
}

async function comparePassword(user, candidatePassword) {
  return bcrypt.compare(candidatePassword, user.password);
}

async function findOrCreateSocialUser({ email, displayName, photoURL, firebaseUid }) {
  const existing = await findByEmail(email);
  if (existing) return existing;

  // Generate a unique username from display name
  let base = (displayName || email.split('@')[0]).replace(/[^a-zA-Z0-9_]/g, '').slice(0, 20) || 'user';
  let username = base;
  let attempt = 1;
  while (await findByUsername(username)) {
    username = `${base}${attempt++}`;
  }

  const now = new Date().toISOString();
  const docRef = usersCollection.doc();
  const user = {
    username,
    usernameLower: username.toLowerCase(),
    email: normalizeEmail(email),
    designation: '',
    password: null,
    firebaseUid: firebaseUid || null,
    photoURL: photoURL || '',
    createdAt: now,
    updatedAt: now,
  };
  await docRef.set(user);
  return { id: docRef.id, ...user };
}

module.exports = {
  comparePassword,
  createUser,
  findById,
  findByEmail,
  findByUsername,
  findConflict,
  findOrCreateSocialUser,
  publicUser,
  updatePassword,
  updateUser,
};
