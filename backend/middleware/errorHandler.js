// Last stop for errors no route answered itself: a malformed JSON body, a
// refused CORS origin, a bug. Express's own handler sends an HTML page with
// the stack trace (file paths included) whenever NODE_ENV is not 'production'
// -- e.g. `npm start` outside Docker. This one logs the error and sends only a
// short JSON message.
module.exports = function errorHandler(err, _req, res, next) {
  // A response already under way can only be cut off, which Express does.
  if (res.headersSent) return next(err);
  const status = Number.isInteger(err.status) && err.status >= 400 && err.status < 600 ? err.status : 500;
  if (status >= 500) console.error('Unhandled request error:', err);
  let message = 'Server error';
  if (err.type === 'entity.parse.failed') message = 'The request body is not valid JSON.';
  else if (status < 500) message = 'Invalid request.';
  return res.status(status).json({ message });
};
