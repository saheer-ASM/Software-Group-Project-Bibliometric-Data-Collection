const bcrypt = require('bcryptjs');
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

async function createUser({ username, email, designation, password }) {
  const now = new Date().toISOString();
  const hashedPassword = await bcrypt.hash(password, 12);

  if (!usersCollection) {
    const id = nextMemoryId();
    const user = {
      id,
      username: normalizeUsername(username),
      usernameLower: normalizeUsername(username).toLowerCase(),
      email: normalizeEmail(email),
      designation: designation.trim(),
      password: hashedPassword,
      createdAt: now,
      updatedAt: now,
    };

    memoryUsers.set(id, user);
    return cloneUser(user);
  }

  const docRef = usersCollection.doc();
  const user = {
    username: normalizeUsername(username),
    usernameLower: normalizeUsername(username).toLowerCase(),
    email: normalizeEmail(email),
    designation: designation.trim(),
    password: hashedPassword,
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

async function updatePassword(id, newPassword) {
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
  return bcrypt.compare(candidatePassword, user.password);
}

module.exports = {
  comparePassword,
  createUser,
  findById,
  findByEmail,
  findByUsername,
  findConflict,
  publicUser,
  updatePassword,
  updateUser,
};
