const path = require('path');
const dotenv = require('dotenv');
const { Pool } = require('pg');

// backend/.env is primary. The research pipeline env is a local fallback.
if (!process.env.DB_HOST) {
  dotenv.config({
    path: process.env.DB_ENV_PATH || path.resolve(__dirname, '..', '..', 'scripts_db', '.env'),
  });
}

const isLocalDatabase = /^(localhost|127\.0\.0\.1)$/i.test(process.env.DB_HOST || '');

module.exports = new Pool({
  host: process.env.DB_HOST,
  port: Number(process.env.DB_PORT || 5432),
  database: process.env.DB_NAME,
  user: process.env.DB_USER,
  password: process.env.DB_PASSWORD,
  ssl: process.env.DB_SSLMODE === 'disable' || isLocalDatabase
    ? false
    : { rejectUnauthorized: false },
  max: 5,
  connectionTimeoutMillis: 10000,
});
