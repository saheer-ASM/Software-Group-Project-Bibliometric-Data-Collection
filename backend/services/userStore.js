const bcrypt = require('bcryptjs');
const admin = require('../config/firebase');

const db = admin.firestore();
const users = db.collection('registeredUsers');

function clean(value) {
  return String(value || '').trim();
}

function publicUser(doc) {
  const data = doc.data();

  return {
    id: doc.id,
    fullName: data.fullName,
    email: data.email,
    designation: data.designation,
    createdAt: data.createdAt,
    updatedAt: data.updatedAt,
  };
}

async function findByEmail(email) {
  const snapshot = await users
    .where('emailLower', '==', clean(email).toLowerCase())
    .limit(1)
    .get();

  if (snapshot.empty) return null;
  const doc = snapshot.docs[0];
  return { id: doc.id, ...doc.data() };
}

async function findByFullName(fullName) {
  const snapshot = await users
    .where('fullNameLower', '==', clean(fullName).toLowerCase())
    .limit(1)
    .get();

  if (snapshot.empty) return null;
  const doc = snapshot.docs[0];
  return { id: doc.id, ...doc.data() };
}

async function findByEmailOrFullName(identifier) {
  const value = clean(identifier);
  if (value.includes('@')) {
    return findByEmail(value);
  }

  return findByFullName(value);
}

async function createUser({ fullName, email, designation, password }) {
  const normalizedFullName = clean(fullName);
  const normalizedEmail = clean(email).toLowerCase();
  const normalizedDesignation = clean(designation);

  const existingEmail = await findByEmail(normalizedEmail);
  if (existingEmail) {
    const error = new Error('Email already registered');
    error.statusCode = 409;
    throw error;
  }

  const existingName = await findByFullName(normalizedFullName);
  if (existingName) {
    const error = new Error('Full name already registered');
    error.statusCode = 409;
    throw error;
  }

  const passwordHash = await bcrypt.hash(password, 12);
  const now = new Date().toISOString();

  const doc = await users.add({
    fullName: normalizedFullName,
    fullNameLower: normalizedFullName.toLowerCase(),
    email: normalizedEmail,
    emailLower: normalizedEmail,
    designation: normalizedDesignation,
    passwordHash,
    createdAt: now,
    updatedAt: now,
  });

  const created = await doc.get();
  return publicUser(created);
}

async function verifyUser(identifier, password) {
  const user = await findByEmailOrFullName(identifier);
  if (!user) return null;

  const matches = await bcrypt.compare(password, user.passwordHash);
  if (!matches) return null;

  return {
    id: user.id,
    fullName: user.fullName,
    email: user.email,
    designation: user.designation,
    createdAt: user.createdAt,
    updatedAt: user.updatedAt,
  };
}

async function findPublicById(id) {
  const doc = await users.doc(id).get();
  if (!doc.exists) return null;
  return publicUser(doc);
}

module.exports = {
  createUser,
  findPublicById,
  verifyUser,
};
