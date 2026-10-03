const bcrypt = require('bcryptjs');
const admin = require('firebase-admin');
const db = require('../config/firebase');

const usersCollection = db ? db.collection('users') : null;
const memoryUsers = new Map();
let memoryUserCounter = 1;

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
    emailVerified: data.emailVerified === true,
    // Profiles created before this field existed are complete.
    profileCompleted: data.profileCompleted !== false,
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

function cloneUser(user) {
  return user ? { ...user } : null;
}

function nextMemoryId() {
  return String(memoryUserCounter++);
}

function findMemoryByUsername(username) {
  const normalized = normalizeUsername(username).toLowerCase();
  return [...memoryUsers.values()].find((user) => user.usernameLower === normalized) || null;
}

function findMemoryByEmail(email) {
  const normalized = normalizeEmail(email);
  return [...memoryUsers.values()].find((user) => user.email === normalized) || null;
}

async function findById(id) {
  if (!usersCollection) {
    return cloneUser(memoryUsers.get(String(id)));
  }

  const doc = await usersCollection.doc(id).get();
  return userFromDoc(doc);
}

async function findByUsername(username) {
  if (!usersCollection) {
    return cloneUser(findMemoryByUsername(username));
  }

  const snapshot = await usersCollection
    .where('usernameLower', '==', normalizeUsername(username).toLowerCase())
    .limit(1)
    .get();

  if (snapshot.empty) return null;
  return userFromDoc(snapshot.docs[0]);
}

async function findByEmail(email) {
  if (!usersCollection) {
    return cloneUser(findMemoryByEmail(email));
  }

  const snapshot = await usersCollection.where('email', '==', normalizeEmail(email)).limit(1).get();

  if (snapshot.empty) return null;
  return userFromDoc(snapshot.docs[0]);
}

async function findConflict({ username, email, excludeId }) {
  if (!usersCollection) {
    const usernameMatch = username ? findMemoryByUsername(username) : null;
    const emailMatch = email ? findMemoryByEmail(email) : null;

    return [usernameMatch, emailMatch].find((user) => user && user.id !== excludeId) || null;
  }

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
  if (!usersCollection) {
    const id = nextMemoryId();
    const user = {
      id,
      username: normalizeUsername(username),
      usernameLower: normalizeUsername(username).toLowerCase(),
      email: normalizedEmail,
      designation: designation.trim(),
      password: hashedPassword,
      createdAt: now,
      updatedAt: now,
    };

    memoryUsers.set(id, user);
    return cloneUser(user);
  }

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

// Profile for an account whose password is managed by Firebase Authentication.
// No password (or password hash) is stored here — Firebase owns the credential.
// profileCompleted: false for accounts created by a first Google sign-in, until
// the user adds a designation and links a password (/api/auth/complete-profile).
async function createFirebaseUser({ username, email, designation, firebaseUid, emailVerified = false, profileCompleted = true }) {
  const now = new Date().toISOString();
  const user = {
    username: normalizeUsername(username),
    usernameLower: normalizeUsername(username).toLowerCase(),
    email: normalizeEmail(email),
    designation: (designation || '').trim(),
    password: null,
    firebaseUid,
    emailVerified,
    profileCompleted,
    createdAt: now,
    updatedAt: now,
  };

  if (!usersCollection) {
    const existing = [...memoryUsers.values()].find((u) => u.firebaseUid === firebaseUid);
    if (existing) return cloneUser(existing);
    const id = nextMemoryId();
    memoryUsers.set(id, { id, ...user });
    return cloneUser(memoryUsers.get(id));
  }

  // The document ID is the Firebase uid, and create() fails if it already
  // exists, so two simultaneous first logins can never produce two profiles
  // for the same Firebase account.
  const docRef = usersCollection.doc(firebaseUid);
  try {
    await docRef.create(user);
  } catch (err) {
    if (err.code !== 6) throw err; // 6 = ALREADY_EXISTS
    return findById(firebaseUid);
  }
  return { id: docRef.id, ...user };
}

async function findByFirebaseUid(firebaseUid) {
  if (!firebaseUid) return null;
  if (!usersCollection) {
    return cloneUser([...memoryUsers.values()].find((u) => u.firebaseUid === firebaseUid) || null);
  }

  const snapshot = await usersCollection.where('firebaseUid', '==', firebaseUid).limit(1).get();
  if (snapshot.empty) return null;
  return userFromDoc(snapshot.docs[0]);
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

  if (!usersCollection) {
    const existing = memoryUsers.get(String(id));
    if (!existing) return null;

    const updated = {
      ...existing,
      ...cleanUpdates,
    };

    memoryUsers.set(String(id), updated);
    return cloneUser(updated);
  }

  await usersCollection.doc(id).update(cleanUpdates);
  return findById(id);
}

async function updatePassword(id, newPassword, { syncFirebase = true } = {}) {
  const user = await findById(id);
  if (!user) return;

  // Firebase-managed account: the password lives only in Firebase Authentication.
  // Clear any hash left over from older versions instead of storing a new one.
  if (user.firebaseUid) {
    if (syncFirebase) {
      await admin.auth().updateUser(user.firebaseUid, { password: newPassword });
    }
    await updateUser(id, { password: null });
    return;
  }

  const hashedPassword = await bcrypt.hash(newPassword, 12);

  if (!usersCollection) {
    const existing = memoryUsers.get(String(id));
    if (!existing) return;

    memoryUsers.set(String(id), {
      ...existing,
      password: hashedPassword,
      updatedAt: new Date().toISOString(),
    });
    return;
  }

  await usersCollection.doc(id).update({
    password: hashedPassword,
    updatedAt: new Date().toISOString(),
  });

}

async function comparePassword(user, candidatePassword) {
  if (!user.password) return false;
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
  createFirebaseUser,
  createUser,
  findByFirebaseUid,
  findById,
  findByEmail,
  findByUsername,
  findConflict,
  findOrCreateSocialUser,
  publicUser,
  updatePassword,
  updateUser,
};
