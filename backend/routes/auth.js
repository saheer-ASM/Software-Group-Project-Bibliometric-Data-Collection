const express = require('express');
const jwt = require('jsonwebtoken');
const admin = require('firebase-admin');
const authMiddleware = require('../middleware/auth');
const userStore = require('../services/firebaseUserStore');

const router = express.Router();

function signToken(id) {
  return jwt.sign({ id }, process.env.JWT_SECRET, {
    expiresIn: process.env.JWT_EXPIRES_IN || '7d',
  });
}

// POST /api/auth/register
router.post('/register', async (req, res) => {
  try {
    const { username, email, designation, password } = req.body;

    if (!username || !email || !designation || !password) {
      return res.status(400).json({ message: 'All fields are required' });
    }
    if (username.trim().length < 3) {
      return res.status(400).json({ message: 'Username must be at least 3 characters' });
    }
    if (password.length < 8) {
      return res.status(400).json({ message: 'Password must be at least 8 characters' });
    }

    const existingUser = await userStore.findConflict({ username, email });
    if (existingUser) {
      const field = existingUser.email === email.trim().toLowerCase() ? 'Email' : 'Username';
      return res.status(409).json({ message: `${field} already in use` });
    }

    const user = await userStore.createUser({ username, email, designation, password });
    const token = signToken(user.id);

    res.status(201).json({
      token,
      user: userStore.publicUser(user),
    });
  } catch (err) {
    res.status(500).json({ message: 'Server error', error: err.message });
  }
});

// POST /api/auth/login
router.post('/login', async (req, res) => {
  try {
    const { username, password } = req.body;

    if (!username || !password) {
      return res.status(400).json({ message: 'Username and password are required' });
    }

    const user = await userStore.findByUsername(username);
    if (!user || !(await userStore.comparePassword(user, password))) {
      return res.status(401).json({ message: 'Invalid username or password' });
    }

    const token = signToken(user.id);
    res.json({
      token,
      user: userStore.publicUser(user),
    });
  } catch (err) {
    res.status(500).json({ message: 'Server error', error: err.message });
  }
});

// POST /api/auth/social  (Google / GitHub sign-in)
router.post('/social', async (req, res) => {
  try {
    const { idToken } = req.body;
    if (!idToken) return res.status(400).json({ message: 'ID token required' });

    const decoded = await admin.auth().verifyIdToken(idToken);
    const { email, name, picture, uid } = decoded;

    if (!email) return res.status(400).json({ message: 'No email in token' });

    const user = await userStore.findOrCreateSocialUser({ email, displayName: name, photoURL: picture, firebaseUid: uid });
    const token = signToken(user.id);
    res.json({ token, user: userStore.publicUser(user) });
  } catch (err) {
    res.status(401).json({ message: 'Social sign-in failed', error: err.message });
  }
});

// POST /api/auth/reset-password
// Called after the user completes Firebase's "forgot password" email flow
// (confirmPasswordReset + sign-in on the frontend). Keeps our own bcrypt
// password store in sync with the password the user just set in Firebase.
router.post('/reset-password', async (req, res) => {
  try {
    const { idToken, newPassword } = req.body;
    if (!idToken || !newPassword) {
      return res.status(400).json({ message: 'ID token and new password are required' });
    }
    if (newPassword.length < 8) {
      return res.status(400).json({ message: 'Password must be at least 8 characters' });
    }

    const decoded = await admin.auth().verifyIdToken(idToken);
    if (!decoded.email) return res.status(400).json({ message: 'No email in token' });

    const user = await userStore.findByEmail(decoded.email);
    if (!user) return res.status(404).json({ message: 'No account found for this email' });

    await userStore.updatePassword(user.id, newPassword, { syncFirebase: false });

    const token = signToken(user.id);
    res.json({ token, user: userStore.publicUser(user) });
  } catch (err) {
    res.status(401).json({ message: 'Password reset failed', error: err.message });
  }
});

// GET /api/auth/profile  (protected)
router.get('/profile', authMiddleware, (req, res) => {
  res.json(userStore.publicUser(req.user));
});

// PUT /api/auth/profile  (protected)
router.put('/profile', authMiddleware, async (req, res) => {
  try {
    const { username, email, designation } = req.body;
    const updates = {};
    if (username) updates.username = username;
    if (email) updates.email = email;
    if (designation) updates.designation = designation;

    if (updates.username && updates.username.trim().length < 3) {
      return res.status(400).json({ message: 'Username must be at least 3 characters' });
    }

    if (updates.username || updates.email) {
      const conflict = await userStore.findConflict({
        username: updates.username,
        email: updates.email,
        excludeId: req.user.id,
      });
      if (conflict) {
        return res.status(409).json({ message: 'Username or email already taken' });
      }
    }

    const updated = await userStore.updateUser(req.user.id, updates);

    res.json(userStore.publicUser(updated));
  } catch (err) {
    res.status(500).json({ message: 'Server error', error: err.message });
  }
});

// PUT /api/auth/change-password  (protected)
router.put('/change-password', authMiddleware, async (req, res) => {
  try {
    const { email, newPassword, confirmPassword } = req.body;

    if (!email || !newPassword || !confirmPassword) {
      return res.status(400).json({ message: 'All fields are required' });
    }
    if (newPassword !== confirmPassword) {
      return res.status(400).json({ message: 'Passwords do not match' });
    }
    if (newPassword.length < 8) {
      return res.status(400).json({ message: 'Password must be at least 8 characters' });
    }
    if (req.user.email !== email.trim().toLowerCase()) {
      return res.status(400).json({ message: 'Email does not match your account' });
    }

    await userStore.updatePassword(req.user.id, newPassword);

    res.json({ message: 'Password updated successfully' });
  } catch (err) {
    res.status(500).json({ message: 'Server error', error: err.message });
  }
});

module.exports = router;
