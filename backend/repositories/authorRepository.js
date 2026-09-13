const pool = require('../db/pool');

async function findByName(name) {
  const { rows } = await pool.query(
    `SELECT a.author_id, a.name, a.affiliation, a.email,
            m.h_index, m.c_index, m.nm_index,
            m.total_citations, m.total_self_citations, m.total_publications
     FROM   authors a
     LEFT JOIN author_metrics m ON m.author_id = a.author_id
     WHERE  to_tsvector('english', a.name) @@ plainto_tsquery('english', $1)
     ORDER  BY ts_rank(to_tsvector('english', a.name), plainto_tsquery('english', $1)) DESC
     LIMIT  20`,
    [name]
  );
  return rows;
}

async function findById(authorId) {
  const { rows } = await pool.query(
    `SELECT a.author_id, a.name, a.affiliation, a.email,
            m.h_index, m.c_index, m.nm_index,
            m.total_citations, m.total_self_citations, m.total_publications
     FROM   authors a
     LEFT JOIN author_metrics m ON m.author_id = a.author_id
     WHERE  a.author_id = $1`,
    [authorId]
  );
  return rows[0] || null;
}

async function getPublications(authorId, { field, year } = {}) {
  const conditions = ['ap.author_id = $1'];
  const params = [authorId];

  if (year) {
    params.push(year);
    conditions.push(`p.year = $${params.length}`);
  }

  if (field) {
    params.push(field);
    conditions.push(`EXISTS (
      SELECT 1 FROM publication_fields pf
      JOIN fields f ON f.field_id = pf.field_id
      WHERE pf.publication_id = p.publication_id AND f.name ILIKE $${params.length}
    )`);
  }

  const where = conditions.join(' AND ');

  const { rows } = await pool.query(
    `SELECT p.publication_id, p.title, p.year, p.venue, p.doi,
            (SELECT COUNT(*) FROM citations c WHERE c.publication_id = p.publication_id)                           AS total_citations,
            (SELECT COUNT(*) FROM citations c WHERE c.publication_id = p.publication_id AND c.is_self_citation)    AS self_citations,
            ap.contribution_order,
            COALESCE(
              json_agg(DISTINCT f.name) FILTER (WHERE f.name IS NOT NULL), '[]'
            ) AS fields
     FROM   author_publications ap
     JOIN   publications p ON p.publication_id = ap.publication_id
     LEFT JOIN publication_fields pf ON pf.publication_id = p.publication_id
     LEFT JOIN fields f ON f.field_id = pf.field_id
     WHERE  ${where}
     GROUP  BY p.publication_id, p.title, p.year, p.venue, p.doi, ap.contribution_order
     ORDER  BY total_citations DESC`,
    params
  );
  return rows;
}

async function getCoAuthors(authorId, publicationId) {
  const { rows } = await pool.query(
    `SELECT a.author_id, a.name, ap.contribution_order
     FROM   author_publications ap
     JOIN   authors a ON a.author_id = ap.author_id
     WHERE  ap.publication_id = $1 AND ap.author_id <> $2
     ORDER  BY ap.contribution_order`,
    [publicationId, authorId]
  );
  return rows;
}

async function upsertMetrics(authorId, metrics) {
  await pool.query(
    `INSERT INTO author_metrics
       (author_id, h_index, c_index, nm_index, total_citations, total_self_citations, total_publications, calculated_at)
     VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
     ON CONFLICT (author_id) DO UPDATE SET
       h_index              = EXCLUDED.h_index,
       c_index              = EXCLUDED.c_index,
       nm_index             = EXCLUDED.nm_index,
       total_citations      = EXCLUDED.total_citations,
       total_self_citations = EXCLUDED.total_self_citations,
       total_publications   = EXCLUDED.total_publications,
       calculated_at        = NOW()`,
    [
      authorId,
      metrics.hIndex,
      metrics.cIndex,
      metrics.nmIndex,
      metrics.totalCitations,
      metrics.totalSelfCitations,
      metrics.totalPublications,
    ]
  );
}

module.exports = { findByName, findById, getPublications, getCoAuthors, upsertMetrics };
