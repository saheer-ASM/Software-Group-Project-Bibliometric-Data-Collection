const userStore = require('../services/firebaseUserStore');
const sessionToken = require('../services/sessionToken');

module.exports = async function authMiddleware(req, res, next) {
  const authHeader = req.headers.authorization;
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return res.status(401).json({ message: 'No token provided' });
  }

  const token = authHeader.split(' ')[1];
  try {
    const decoded = sessionToken.verify(token);
    req.user = await userStore.findById(decoded.id);
    if (!req.user) return res.status(401).json({ message: 'User not found' });
    // Signed out, or password reset, since this token was issued.
    if (!sessionToken.isCurrent(decoded, req.user)) {
      return res.status(401).json({ message: 'Your session has ended. Please sign in again.' });
    }
    next();
  } catch {
    return res.status(401).json({ message: 'Invalid or expired token' });
  }
};
