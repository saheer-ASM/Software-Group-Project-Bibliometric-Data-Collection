const { Pool } = require('pg');

const pool = new Pool({
  host:     process.env.PG_HOST     || 'localhost',
  port:     parseInt(process.env.PG_PORT || '5432', 10),
  database: process.env.PG_DATABASE || 'scholarmetrics',
  user:     process.env.PG_USER     || 'postgres',
  password: process.env.PG_PASSWORD || '',
});

module.exports = pool;
