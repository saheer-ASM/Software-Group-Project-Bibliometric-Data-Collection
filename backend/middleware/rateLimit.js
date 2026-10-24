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

//
// The client is req.ip, which is only the real visitor when Express trusts the
// proxy in front of it (TRUST_PROXY, see server.js). Without that, behind
// nginx every visitor has nginx's address and shares a single counter.

function clientKey(req) {
  // The socket address is the fallback so a missing proxy setting cannot
  // collapse every caller onto a single undefined key.
  return req.ip || req.socket?.remoteAddress || 'unknown';
}

/**
 * A limiter with its own counters. `key(req)` picks who is counted; the
 * default is the client address.
 */
function createRateLimit({ windowMs, max, key = clientKey }) {
  // client key -> { count, resetAt }
  const hits = new Map();
  let lastSweep = Date.now();

  // Keeps the map from growing without bound on a long-running process.
  function sweep(now) {
    for (const [hitKey, entry] of hits) {
      if (entry.resetAt <= now) hits.delete(hitKey);
    }
  }

  return function rateLimit(req, res, next) {
    const now = Date.now();
    if (now - lastSweep > windowMs) {
      sweep(now);
      lastSweep = now;
    }

    const hitKey = key(req);
    const entry = hits.get(hitKey);

    if (!entry || entry.resetAt <= now) {
      hits.set(hitKey, { count: 1, resetAt: now + windowMs });
      res.setHeader('X-RateLimit-Limit', max);
      res.setHeader('X-RateLimit-Remaining', max - 1);
      return next();
    }

    entry.count += 1;

    if (entry.count > max) {
      const retryAfter = Math.max(1, Math.ceil((entry.resetAt - now) / 1000));
      res.setHeader('Retry-After', retryAfter);
      res.setHeader('X-RateLimit-Limit', max);
      res.setHeader('X-RateLimit-Remaining', 0);
      return res.status(429).json({
        message: 'Too many requests. Please slow down and try again shortly.',
        retryAfter,
      });
    }

    res.setHeader('X-RateLimit-Limit', max);
    res.setHeader('X-RateLimit-Remaining', max - entry.count);
    return next();
  };
}

// The whole /api surface.
const rateLimit = createRateLimit({
  windowMs: Number(process.env.RATE_LIMIT_WINDOW_MS || 60_000),
  max: Number(process.env.RATE_LIMIT_MAX_REQUESTS || 300),
});

// The routes that scan the bibliometric tables (search, compare, author
// suggestions). Each such query blocks the process for its whole run -- the
// SQLite driver is synchronous -- so they get a much smaller budget, shared
// between them. Mounted after authMiddleware, so it counts per account: one
// account cannot spread its requests over several addresses.
const heavyQueryLimit = createRateLimit({
  windowMs: Number(process.env.HEAVY_RATE_LIMIT_WINDOW_MS || 60_000),
  max: Number(process.env.HEAVY_RATE_LIMIT_MAX_REQUESTS || 60),
  key: (req) => (req.user?.id ? `user:${req.user.id}` : `ip:${clientKey(req)}`),
});

module.exports = rateLimit;
module.exports.createRateLimit = createRateLimit;
module.exports.heavyQueryLimit = heavyQueryLimit;
