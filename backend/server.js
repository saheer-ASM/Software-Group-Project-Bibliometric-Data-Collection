// Configuration comes from backend/.env (or the container's environment) only.
// A second load from a file named "env" in the repository root was removed: a
// stray file there could silently inject settings such as JWT_SECRET.
require('dotenv').config();
const express = require('express');
const { getApps } = require('firebase-admin/app');
const pool = require('./config/database');
const authRoutes = require('./routes/auth');
const authorRoutes = require('./routes/authors');
const searchRoutes = require('./routes/search');
const statsRoutes = require('./routes/stats');
const compareRoutes = require('./routes/compare');
const libraryRoutes = require('./routes/library');
const rateLimit = require('./middleware/rateLimit');
const errorHandler = require('./middleware/errorHandler');
const createCors = require('./middleware/cors');

const app = express();
// Do not advertise the framework (X-Powered-By: Express). The other security
// headers are set once, for the whole site, by the edge nginx
// (production/nginx/default.conf).
app.disable('x-powered-by');

// Which proxies may report the client address in X-Forwarded-For. Unset (local
// development, no proxy) leaves req.ip as the socket address. Behind the
// production nginx it must be set (production/compose.yaml), or req.ip is
// nginx's own address and every visitor shares one rate-limit counter.
// Accepts a hop count ("1"), "true", or Express's address list
// ("loopback, uniquelocal").
function parseTrustProxy(value) {
  const trimmed = String(value || '').trim();
  if (!trimmed) return false;
  if (/^\d+$/.test(trimmed)) return Number(trimmed);
  if (trimmed === 'true' || trimmed === 'false') return trimmed === 'true';
  return trimmed;
}
app.set('trust proxy', parseTrustProxy(process.env.TRUST_PROXY));

// Pages on the site's own address (any tunnel link included) and on
// http://localhost:<port> are always allowed (middleware/cors.js). Only OTHER
// sites that must call this API need listing, comma-separated, e.g.
// CORS_ALLOWED_ORIGINS=https://scholarmetrics.example.com
const allowedOrigins = (process.env.CORS_ALLOWED_ORIGINS || '')
  .split(',')
  .map((value) => value.trim())
  .filter(Boolean);

app.use(createCors(allowedOrigins));
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
    // Reads a real table: SELECT 1 alone would succeed even when the path
    // points at a file that is not this database. Goes ahead of queued
    // searches, so a busy pool does not read as a dead database.
    await pool.query('SELECT 1 FROM author LIMIT 1', [], { priority: true });
    if (lastDatabaseFailure !== null) {
      console.log(`[db] database ${pool.dbTarget} is readable again`);
      lastDatabaseFailure = null;
    }
    return true;
  } catch (error) {
    const reason = pool.describeDbError(error);
    if (reason !== lastDatabaseFailure) {
      console.error(`[db] database ${pool.dbTarget} is unavailable: ${reason}`);
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
    firebaseAdmin: getApps().length ? 'configured' : 'not_configured',
  };
  const healthy = Object.values(dependencies).every((value) =>
    value === 'connected' || value === 'configured');

  res.status(healthy ? 200 : 503).json({
    status: healthy ? 'ok' : 'degraded',
    dependencies,
  });
});

// Last, after every route: errors no route answered itself.
app.use(errorHandler);

const PORT = process.env.PORT || 5005;
// Defaults to localhost so local development is unchanged. In a container this
// MUST be 0.0.0.0 (set in production/compose.yaml): binding to 'localhost'
// inside a container binds the container's own loopback, so nginx on the Docker
// network would never be able to reach it.
const HOST = process.env.HOST || 'localhost';
app.listen(PORT, HOST, () => {
  console.log(`Server running on http://${HOST}:${PORT}`);
  // The database opens lazily, so without this the first sign of a bad path
  // would be a failed request. Logged, not fatal: /api/health keeps
  // reporting it, and the next query tries again.
  console.log(`[db] SQLite database ${pool.dbTarget} (read-only)`);
  checkDatabase().then((ok) => {
    if (ok) console.log('[db] connected to the database');
  });
});
