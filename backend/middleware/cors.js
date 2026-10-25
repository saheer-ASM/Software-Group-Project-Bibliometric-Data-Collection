// Which web pages may call the API from a browser.
//
// Allowed:
// - the site itself: a page whose Origin is the very address this request
//   came in on (scheme + host). Through the production nginx the site and its
//   /api share one address, whatever it is -- http://localhost, or the new
//   https://<random>.trycloudflare.com of every Cloudflare quick tunnel -- so
//   no address has to be listed anywhere. Browsers still send Origin on such
//   requests (POST), which is why this check is needed at all.
// - http://localhost:<port>: local development (the React dev server).
// - the extra origins in CORS_ALLOWED_ORIGINS (comma-separated).
//
// Everything else -- a page on another website -- gets 403. That page cannot
// make the browser send this site's Host together with a matching Origin.
//
// The scheme comes from req.protocol, which follows X-Forwarded-Proto only
// when the request came through a trusted proxy (TRUST_PROXY, set for the
// production nginx; nginx itself believes that header only from Cloudflare).
const cors = require('cors');

const LOCAL_DEVELOPMENT = /^http:\/\/localhost:\d+$/;

function isAllowed(req, origin, allowedOrigins) {
  return !origin
    || LOCAL_DEVELOPMENT.test(origin)
    || allowedOrigins.includes(origin)
    || origin === `${req.protocol}://${req.get('host')}`;
}

module.exports = function createCors(allowedOrigins = []) {
  return cors((req, callback) => {
    const origin = req.get('origin');
    if (isAllowed(req, origin, allowedOrigins)) {
      return callback(null, { origin: true, credentials: true });
    }
    console.warn(`CORS: refused a request from ${origin} (not this site's address, localhost or CORS_ALLOWED_ORIGINS)`);
    const error = new Error('Not allowed by CORS');
    error.status = 403;
    return callback(error);
  });
};
