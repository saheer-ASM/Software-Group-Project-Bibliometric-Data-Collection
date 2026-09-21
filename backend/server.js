const path = require('path');
require('dotenv').config({ path: path.resolve(__dirname, '..', 'env') });
require('dotenv').config();
const express = require('express');
const cors = require('cors');
const admin = require('firebase-admin');
const pool = require('./config/database');
const authRoutes = require('./routes/auth');
const authorRoutes = require('./routes/authors');
const searchRoutes = require('./routes/search');
const statsRoutes = require('./routes/stats');
const compareRoutes = require('./routes/compare');
const libraryRoutes = require('./routes/library');

const app = express();

app.use(
  cors({
    origin(origin, callback) {
      if (!origin || /^http:\/\/localhost:\d+$/.test(origin)) {
        return callback(null, true);
      }

      return callback(new Error('Not allowed by CORS'));
    },
    credentials: true,
  })
);
app.use(express.json());

app.use('/api/auth', authRoutes);
app.use('/api/search', searchRoutes);
app.use('/api/stats', statsRoutes);
app.use('/api/authors', authorRoutes);
app.use('/api/compare', compareRoutes);
app.use('/api/library', libraryRoutes);

app.get('/api/health', async (_req, res) => {
  let database = 'connected';
  try {
    await pool.query('SELECT 1');
  } catch (_error) {
    database = 'unavailable';
  }

  const dependencies = {
    database,
    firebaseAdmin: admin.apps.length ? 'configured' : 'not_configured',
  };
  const healthy = Object.values(dependencies).every((value) =>
    value === 'connected' || value === 'configured');

  res.status(healthy ? 200 : 503).json({
    status: healthy ? 'ok' : 'degraded',
    dependencies,
  });
});

const PORT = process.env.PORT || 5005;
app.listen(PORT, 'localhost', () => console.log(`Server running on http://localhost:${PORT}`));
