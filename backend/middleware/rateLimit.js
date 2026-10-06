// Fixed-window, per-client request limiter.
//
// The project had no rate limiting of any kind, so this is a single shared
// middleware applied to the whole /api surface rather than a one-off guard on
// the publications route -- an endpoint-specific limiter would leave every
// other route open and give two different behaviours to reason about.
//
// Deliberately dependency-free and in-process: the API runs as one Node
// process behind nginx, so a local counter is accurate for this deployment.
// Behind multiple API replicas the counters would be per-replica, which is
// the point at which a shared store (or express-rate-limit with one) becomes
// worth the dependency.

const WINDOW_MS = Number(process.env.RATE_LIMIT_WINDOW_MS || 60_000);
const MAX_REQUESTS = Number(process.env.RATE_LIMIT_MAX_REQUESTS || 300);

// client key -> { count, resetAt }
const hits = new Map();

// Keeps the map from growing without bound on a long-running process.
function sweep(now) {
  for (const [key, entry] of hits) {
    if (entry.resetAt <= now) hits.delete(key);
  }
}

let lastSweep = Date.now();

function clientKey(req) {
  // req.ip honours trust proxy when it is configured; the socket address is
  // the fallback so a missing proxy setting cannot collapse every caller onto
  // a single undefined key.
  return req.ip || req.socket?.remoteAddress || 'unknown';
}

function rateLimit(req, res, next) {
  const now = Date.now();
  if (now - lastSweep > WINDOW_MS) {
    sweep(now);
    lastSweep = now;
  }

  const key = clientKey(req);
  const entry = hits.get(key);

  if (!entry || entry.resetAt <= now) {
    hits.set(key, { count: 1, resetAt: now + WINDOW_MS });
    res.setHeader('X-RateLimit-Limit', MAX_REQUESTS);
    res.setHeader('X-RateLimit-Remaining', MAX_REQUESTS - 1);
    return next();
  }

  entry.count += 1;

  if (entry.count > MAX_REQUESTS) {
    const retryAfter = Math.max(1, Math.ceil((entry.resetAt - now) / 1000));
    res.setHeader('Retry-After', retryAfter);
    res.setHeader('X-RateLimit-Limit', MAX_REQUESTS);
    res.setHeader('X-RateLimit-Remaining', 0);
    return res.status(429).json({
      message: 'Too many requests. Please slow down and try again shortly.',
      retryAfter,
    });
  }

  res.setHeader('X-RateLimit-Limit', MAX_REQUESTS);
  res.setHeader('X-RateLimit-Remaining', MAX_REQUESTS - entry.count);
  return next();
}

module.exports = rateLimit;
