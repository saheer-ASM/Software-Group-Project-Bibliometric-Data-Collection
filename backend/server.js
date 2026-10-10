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
const rateLimit = require('./middleware/rateLimit');

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

// Applied to the whole API, before the routers, so every endpoint gets the
// same limit rather than only the ones added since.
app.use('/api', rateLimit);

app.use('/api/auth', authRoutes);
app.use('/api/search', searchRoutes);
app.use('/api/stats', statsRoutes);
app.use('/api/authors', authorRoutes);
app.use('/api/compare', compareRoutes);
app.use('/api/library', libraryRoutes);

// Last database failure reported, so the log records each change of state
// once instead of repeating the same line on every 30-second health probe.
let lastDatabaseFailure = null;

async function checkDatabase() {
  try {
    await pool.query('SELECT 1');
    if (lastDatabaseFailure !== null) {
      console.log(`[db] PostgreSQL at ${pool.dbTarget} is reachable again`);
      lastDatabaseFailure = null;
    }
    return true;
  } catch (error) {
    const reason = pool.describeDbError(error);
    if (reason !== lastDatabaseFailure) {
      console.error(`[db] PostgreSQL at ${pool.dbTarget} is unavailable: ${reason}`);
      lastDatabaseFailure = reason;
    }
    return false;
  }
}

app.get('/api/health', async (_req, res) => {
  // The reason is logged server-side only; this endpoint is public through
  // nginx, so it reports the state without the details.
  const database = (await checkDatabase()) ? 'connected' : 'unavailable';

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
app.listen(PORT, HOST, () => {
  console.log(`Server running on http://${HOST}:${PORT}`);
  // pg connects lazily, so without this the first sign of a bad database
  // setting would be a failed request. Logged, not fatal: a transient outage
  // should not crash-loop the container, and /api/health keeps reporting it.
  console.log(`[db] PostgreSQL target ${pool.dbTarget}, TLS ${pool.dbTls}`);
  checkDatabase().then((ok) => {
    if (ok) console.log('[db] connected to PostgreSQL');
  });
});
