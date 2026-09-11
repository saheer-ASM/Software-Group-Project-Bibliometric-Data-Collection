const jwt = require('jsonwebtoken');
const crypto = require('crypto');
const userStore = require('../services/firebaseUserStore');
const JWT_SECRET = process.env.JWT_SECRET || 'dev-secret';

async function createOrFindGoogleUser(decoded) {
  const email = decoded.email || '';
  if (!email) return null;

  const username = decoded.name || email.split('@')[0] || 'User';
  let user = await userStore.findByEmail(email);

  if (!user) {
    user = await userStore.createUser({
      username,
      email,
      designation: 'Researcher',
      password: crypto.randomBytes(32).toString('hex'),
    });
  }

  return user;
}

module.exports = async function authMiddleware(req, res, next) {
  const authHeader = req.headers.authorization;
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return res.status(401).json({ message: 'No token provided' });
  }

  const token = authHeader.split(' ')[1];
  try {
    const decoded = jwt.verify(token, JWT_SECRET);
    req.user = await userStore.findById(decoded.id);
    if (!req.user) return res.status(401).json({ message: 'User not found' });
    next();
  } catch {
    const decoded = jwt.decode(token);
    if (decoded && decoded.email) {
      try {
        req.user = await createOrFindGoogleUser(decoded);
        if (req.user) {
          return next();
        }
      } catch {
        // Fall through to the generic auth error below.
      }
    }

    res.status(401).json({ message: 'Invalid or expired token' });
  }
};
