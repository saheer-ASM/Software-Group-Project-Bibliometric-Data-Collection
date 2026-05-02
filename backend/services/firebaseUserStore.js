const bcrypt = require('bcryptjs');
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

async function createUser({ username, email, designation, password }) {
  const now = new Date().toISOString();
  const hashedPassword = await bcrypt.hash(password, 12);
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

  await usersCollection.doc(id).update(cleanUpdates);
  return findById(id);
}

async function updatePassword(id, newPassword) {
  const hashedPassword = await bcrypt.hash(newPassword, 12);
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
  findByUsername,
  findConflict,
  publicUser,
  updatePassword,
  updateUser,
};
