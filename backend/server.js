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

// Extra origins allowed in deployed environments, comma-separated, e.g.
// CORS_ALLOWED_ORIGINS=https://scholarmetrics.example.com
// Unset (the default) leaves the original localhost-only behaviour untouched.
const allowedOrigins = (process.env.CORS_ALLOWED_ORIGINS || '')
  .split(',')
  .map((value) => value.trim())
  .filter(Boolean);

app.use(
  cors({
    origin(origin, callback) {
      if (
        !origin ||
        /^http:\/\/localhost:\d+$/.test(origin) ||
        allowedOrigins.includes(origin)
      ) {
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
// Defaults to localhost so local development is unchanged. In a container this
// MUST be 0.0.0.0 (set in production/compose.yaml): binding to 'localhost'
// inside a container binds the container's own loopback, so nginx on the Docker
// network would never be able to reach it.
const HOST = process.env.HOST || 'localhost';
app.listen(PORT, HOST, () => console.log(`Server running on http://${HOST}:${PORT}`));
