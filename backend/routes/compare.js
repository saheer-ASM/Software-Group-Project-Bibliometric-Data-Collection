const express = require('express');
const pool = require('../config/database');
const authMiddleware = require('../middleware/auth');
const { heavyQueryLimit } = require('../middleware/rateLimit');
const { AUTHOR_ID_PATTERN } = require('../services/libraryAuthors');
const searchIndex = require('../services/searchIndex');

const router = express.Router();

// A comparison can scan author_contribution_weight (when the search index is
// not usable) and holds a database worker while it runs: signed-in users only,
// within the shared search budget.
router.use(authMiddleware, heavyQueryLimit);
const numeric = (value) => (Number.isFinite(Number(value)) ? Number(value) : 0);

// The selected authors' publications, in two interchangeable forms.
//
// From the search index (services/searchIndex.js): one lookup per author.
const INDEXED_PUBLICATIONS_SQL = `
  FROM selected_authors selected
  CROSS JOIN idx.author_publication author_pub ON author_pub.author_id = selected.author_id
  CROSS JOIN publication p ON p.pub_id = author_pub.pub_id`;

// Without it: the ten author slots have no index in openalex.db, so this is a
// full scan of author_contribution_weight. In SQLite CROSS JOIN fixes the join
// order: that table is scanned once (not once per author), each row is checked
// against the MATERIALIZED authors, and only the rows that match are looked up
// in publication.
const SCANNED_PUBLICATIONS_SQL = `
  FROM author_contribution_weight acw
  CROSS JOIN selected_authors selected
  CROSS JOIN publication p ON p.pub_id = acw.pub_id
  WHERE selected.author_id IN (acw.author1id, acw.author2id, acw.author3id,
    acw.author4id, acw.author5id, acw.author6id, acw.author7id,
    acw.author8id, acw.author9id, acw.author10id)`;

router.get('/', async (req, res) => {
  const authorIds = String(req.query.authorIds || '')
    .split(',')
    .map((id) => id.trim())
    .filter(Boolean);
  const uniqueAuthorIds = [...new Set(authorIds)];

  if (uniqueAuthorIds.length < 2 || uniqueAuthorIds.length > 3) {
    return res.status(400).json({ message: 'Select between 2 and 3 unique authors.' });
  }
  if (!uniqueAuthorIds.every((id) => AUTHOR_ID_PATTERN.test(id))) {
    return res.status(400).json({ message: 'Author ids must look like A1234567.' });
  }

  try {
    // Both queries below need the selected authors' publications: from the
    // search index when it is usable, from the full scan otherwise.
    const params = [JSON.stringify(uniqueAuthorIds)];
    const run = (sqlFor) => searchIndex.query(pool.query, {
      indexed: [sqlFor(INDEXED_PUBLICATIONS_SQL), params],
      scan: [sqlFor(SCANNED_PUBLICATIONS_SQL), params],
    });

    const summaryResult = await run((selectedPublications) =>
      `WITH selected_authors AS MATERIALIZED (
         SELECT value AS author_id, key + 1 AS position
         FROM json_each(?1)
       ),
       author_publications AS MATERIALIZED (
         SELECT selected.author_id, selected.position, p.pub_id,
           COALESCE(p.total_citation, 0) AS total_citation
         ${selectedPublications}
       ),
       publication_totals AS (
         SELECT ap.author_id,
           COUNT(*) AS publications,
           COALESCE(SUM(ap.total_citation), 0) AS citations,
           COALESCE(SUM(apac.total_adjusted_citation), 0) AS adjusted_citations
         FROM author_publications ap
         LEFT JOIN author_paper_adjusted_citations apac
           ON apac.cited_pub_id = ap.pub_id AND apac.target_author_id = ap.author_id
         GROUP BY ap.author_id
       ),
       self_citation_totals AS (
         SELECT ap.author_id,
           COUNT(DISTINCT isc.cited_pub_id || '|' || isc.citing_pub_id) AS self_citations
         FROM author_publications ap
         LEFT JOIN influential_self_citations isc
           ON isc.cited_pub_id = ap.pub_id
          AND isc.target_author_id = ap.author_id
          AND isc.isc_value > 0
         GROUP BY ap.author_id
       )
       SELECT selected.author_id, author.author_name, selected.position,
         COALESCE(totals.publications, 0) AS publications,
         COALESCE(totals.citations, 0) AS citations,
         COALESCE(totals.adjusted_citations, 0) AS adjusted_citations,
         COALESCE(self_totals.self_citations, 0) AS self_citations,
         total_cites.total_cites_score,
         total_cites.career_factor,
         nm.nm_index
       FROM selected_authors selected
       JOIN author author ON author.author_id = selected.author_id
       LEFT JOIN publication_totals totals ON totals.author_id = selected.author_id
       LEFT JOIN self_citation_totals self_totals ON self_totals.author_id = selected.author_id
       LEFT JOIN author_total_cites total_cites ON total_cites.author_id = selected.author_id
       LEFT JOIN author_nm_index nm ON nm.author_id = selected.author_id
       ORDER BY selected.position`);

    if (summaryResult.rows.length !== uniqueAuthorIds.length) {
      return res.status(404).json({ message: 'One or more selected authors were not found.' });
    }

    // The CROSS JOINs below make SQLite start from the selected publications
    // and look up their citations, rather than scan the whole citation and
    // influential_self_citations tables. The yearly h-index is a correlated
    // subquery per (author, year), as SQLite has no LATERAL join;
    // total_citation comes along in selected_publications instead of through
    // a second join to publication. DESC NULLS FIRST is PostgreSQL's default
    // order, which SQLite reverses.
    const trendResult = await run((selectedPublications) =>
      `WITH selected_authors AS MATERIALIZED (
         SELECT value AS author_id FROM json_each(?1)
       ),
       selected_publications AS MATERIALIZED (
         SELECT selected.author_id, p.pub_id, p.year, p.total_citation
         ${selectedPublications}
       ),
       publication_years AS (
         SELECT author_id, year, COUNT(*) AS publications
         FROM selected_publications WHERE year IS NOT NULL GROUP BY author_id, year
       ),
       citation_years AS (
         SELECT selected.author_id, citing.year,
           COUNT(DISTINCT citation.pub_id || '|' || citation.cites_pub_id) AS citations
         FROM selected_publications selected
         CROSS JOIN citation citation ON citation.pub_id = selected.pub_id
         CROSS JOIN publication citing ON citing.pub_id = citation.cites_pub_id
         WHERE citing.year IS NOT NULL GROUP BY selected.author_id, citing.year
       ),
       adjusted_years AS (
         SELECT selected.author_id, citing.year,
           COALESCE(SUM(isc.adjusted_citation), 0) AS adjusted_citations
         FROM selected_publications selected
         CROSS JOIN influential_self_citations isc
           ON isc.cited_pub_id = selected.pub_id AND isc.target_author_id = selected.author_id
         CROSS JOIN publication citing ON citing.pub_id = isc.citing_pub_id
         WHERE citing.year IS NOT NULL GROUP BY selected.author_id, citing.year
       ),
       self_citation_years AS (
         SELECT selected.author_id, citing.year,
           COUNT(DISTINCT isc.cited_pub_id || '|' || isc.citing_pub_id) AS self_citations
         FROM selected_publications selected
         CROSS JOIN influential_self_citations isc
           ON isc.cited_pub_id = selected.pub_id
          AND isc.target_author_id = selected.author_id
          AND isc.isc_value > 0
         CROSS JOIN publication citing ON citing.pub_id = isc.citing_pub_id
         WHERE citing.year IS NOT NULL GROUP BY selected.author_id, citing.year
       ),
       keys AS (
         SELECT author_id, year FROM publication_years UNION
         SELECT author_id, year FROM citation_years UNION
         SELECT author_id, year FROM adjusted_years UNION
         SELECT author_id, year FROM self_citation_years
       )
       SELECT keys.author_id, keys.year,
         COALESCE(publication_years.publications, 0) AS publications,
         COALESCE(citation_years.citations, 0) AS citations,
         COALESCE(adjusted_years.adjusted_citations, 0) AS adjusted_citations,
         COALESCE(self_citation_years.self_citations, 0) AS self_citations,
         (SELECT COALESCE(MAX(citation_rank), 0)
          FROM (
            SELECT total_citation,
              ROW_NUMBER() OVER (ORDER BY total_citation DESC NULLS FIRST) AS citation_rank
            FROM selected_publications publications
            WHERE publications.author_id = keys.author_id AND publications.year <= keys.year
          ) ranked
          WHERE total_citation >= citation_rank) AS h_index
       FROM keys
       LEFT JOIN publication_years USING (author_id, year)
       LEFT JOIN citation_years USING (author_id, year)
       LEFT JOIN adjusted_years USING (author_id, year)
       LEFT JOIN self_citation_years USING (author_id, year)
       ORDER BY keys.year`);

    const trendsByAuthor = new Map(uniqueAuthorIds.map((id) => [id, []]));
    trendResult.rows.forEach((row) => trendsByAuthor.get(row.author_id)?.push({
      year: String(row.year),
      publications: Number(row.publications),
      citations: Number(row.citations),
      adjustedCitations: numeric(row.adjusted_citations),
      selfCitations: Number(row.self_citations),
      hIndex: Number(row.h_index),
    }));
    trendsByAuthor.forEach((points) => {
      let totalPublications = 0;
      let totalCitations = 0;
      points.forEach((point) => {
        totalPublications += point.publications;
        totalCitations += point.citations;
        point.totalPublications = totalPublications;
        point.totalCitations = totalCitations;
      });
    });

    return res.json({
      authors: summaryResult.rows.map((row) => ({
        authorId: row.author_id,
        name: row.author_name,
        publications: Number(row.publications),
        citations: numeric(row.citations),
        adjustedCitations: numeric(row.adjusted_citations),
        selfCitations: Number(row.self_citations),
        cScore: numeric(row.total_cites_score),
        careerFactor: numeric(row.career_factor),
        nmIndex: numeric(row.nm_index),
        trendData: trendsByAuthor.get(row.author_id) || [],
      })),
    });
  } catch (error) {
    console.error('Author comparison query failed:', error);
    return res.status(500).json({ message: 'Unable to compare authors.' });
  }
});

module.exports = router;
