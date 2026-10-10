const path = require('path');
const dotenv = require('dotenv');
const { Pool } = require('pg');

// backend/.env is primary. The research pipeline env is a local fallback.
if (!process.env.DB_HOST) {
  dotenv.config({
    path: process.env.DB_ENV_PATH || path.resolve(__dirname, '..', '..', 'scripts_db', '.env'),
  });
}

// pg fills in its own defaults for anything left unset -- host=localhost,
// user=<OS user> -- so a missing DB_HOST would quietly aim the app at a
// database on whatever machine it runs on. These are checked up front so a gap
// in the configuration fails loudly instead.
const REQUIRED_SETTINGS = ['DB_HOST', 'DB_NAME', 'DB_USER', 'DB_PASSWORD'];

function configError(detail) {
  return new Error(
    `PostgreSQL configuration error: ${detail} `
    + '(production/.env for Docker, backend/.env for local development)'
  );
}

function readDatabaseConfig(env) {
  const missing = REQUIRED_SETTINGS.filter((name) => !String(env[name] || '').trim());
  if (missing.length) throw configError(`missing ${missing.join(', ')}`);

  const rawPort = String(env.DB_PORT || '').trim();
  const port = rawPort ? Number(rawPort) : 5432;
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    throw configError('DB_PORT must be a whole number between 1 and 65535');
  }

  const host = env.DB_HOST.trim();
  const isLocalDatabase = /^(localhost|127\.0\.0\.1|::1)$/i.test(host);
  const sslMode = String(env.DB_SSLMODE || '').trim().toLowerCase();

  // Empty keeps the original behaviour: TLS without certificate verification
  // for a remote server, plain TCP for one on this machine. verify-full also
  // checks the certificate and host name, which needs the RDS CA bundle
  // (NODE_EXTRA_CA_CERTS) and the RDS endpoint name rather than an IP.
  let ssl;
  if (sslMode === 'disable') ssl = false;
  else if (sslMode === 'verify-full') ssl = { rejectUnauthorized: true };
  else if (sslMode === 'require') ssl = { rejectUnauthorized: false };
  else if (sslMode === '') ssl = isLocalDatabase ? false : { rejectUnauthorized: false };
  else throw configError(`DB_SSLMODE "${sslMode}" is not supported; use disable, require or verify-full, or leave it empty`);

  return {
    host,
    port,
    database: env.DB_NAME.trim(),
    user: env.DB_USER.trim(),
    password: env.DB_PASSWORD,
    ssl,
  };
}

const config = readDatabaseConfig(process.env);

// One pool for the whole process. Node caches this module, so every route that
// requires it shares these connections instead of opening its own.
const pool = new Pool({
  ...config,
  max: 5,
  connectionTimeoutMillis: 10000,
});

const HINTS = {
  53300: 'the database server has no free connection slots -- another client (pgAdmin, a script) is likely holding them',
  '28P01': 'authentication failed -- check DB_USER and DB_PASSWORD',
  '3D000': 'the database does not exist -- check DB_NAME',
  ECONNREFUSED: 'connection refused -- nothing is accepting connections at that host and port',
  ENOTFOUND: 'host not found -- check DB_HOST',
  EAI_AGAIN: 'DNS lookup failed -- check DB_HOST and the network',
  ETIMEDOUT: 'connection timed out -- check DB_HOST, the network and the AWS security group',
  ECONNRESET: 'connection reset by the server or network',
};

/**
 * A one-line, log-safe reason for a database failure: the error code, a hint,
 * and pg's message with the password scrubbed out in case a driver ever
 * echoes it. Never includes the connection settings themselves.
 */
function describeDbError(error) {
  const code = error && error.code ? String(error.code) : '';
  let message = String((error && error.message) || error || 'unknown error');
  if (config.password) message = message.split(config.password).join('***');
  const hint = HINTS[code];
  if (!hint && /timeout/i.test(message)) {
    return `${message} -- check DB_HOST, the network and the AWS security group`;
  }
  if (!hint && /certificate|self[- ]signed|ssl|tls/i.test(message)) {
    return `${message} -- check DB_SSLMODE`;
  }
  return [code && `[${code}]`, hint, hint ? `(${message})` : message].filter(Boolean).join(' ');
}

// Without a listener, an error on an IDLE pooled connection -- the server
// restarting, RDS maintenance, a dropped network path -- is an unhandled
// 'error' event, and Node terminates the whole process for it.
pool.on('error', (error) => {
  console.error(`[db] idle PostgreSQL connection failed: ${describeDbError(error)}`);
});

module.exports = pool;
// Non-secret descriptions for log lines: where the pool points, and whether TLS
// is on. The user name and password are deliberately not exposed.
module.exports.describeDbError = describeDbError;
module.exports.dbTarget = `${config.host}:${config.port}/${config.database}`;
module.exports.dbTls = config.ssl
  ? (config.ssl.rejectUnauthorized ? 'on, certificate verified' : 'on, certificate not verified')
  : 'off';
