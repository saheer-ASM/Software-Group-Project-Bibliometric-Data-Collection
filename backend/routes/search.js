const express = require('express');
const pool = require('../config/database');

const router = express.Router();
const numeric = (value) => (Number.isFinite(Number(value)) ? Number(value) : 0);

function hIndex(values) {
  return [...values].sort((a, b) => b - a)
    .reduce((result, value, index) => (value >= index + 1 ? index + 1 : result), 0);
}

function trendData(publications, citationImpactByYear = []) {
  const years = new Map();
  publications.forEach((publication) => {
    const key = publication.publishedYear || 'Unknown';
    const value = years.get(key) || {
      name: String(key), publications: 0, citations: 0, adjustedCitations: 0,
    };
    value.publications += 1;
    years.set(key, value);
  });

  citationImpactByYear.forEach((impact) => {
    if (!impact.year) return;
    const key = impact.year;
    const value = years.get(key) || {
      name: String(key), publications: 0, citations: 0, adjustedCitations: 0,
    };
    value.citations = numeric(impact.citations);
    value.adjustedCitations = numeric(impact.adjusted_citations);
    years.set(key, value);
  });

  return [...years.values()].sort((a, b) => String(a.name).localeCompare(String(b.name)));
}

async function fetchAnnualCitationImpact(client, citedPublicationIds, authorId) {
  if (!citedPublicationIds.length) return [];

  const columnResult = await client.query(
    `SELECT column_name
     FROM information_schema.columns
     WHERE table_schema = 'public' AND table_name = 'citation'`
  );
  const columns = new Set(columnResult.rows.map((row) => row.column_name));
  let citedColumn;
  let citingColumn;

  if (columns.has('cited_pub_id') && columns.has('citing_pub_id')) {
    citedColumn = 'cited_pub_id';
    citingColumn = 'citing_pub_id';
  } else if (columns.has('pub_id') && columns.has('cites_pub_id')) {
    citedColumn = 'pub_id';
    citingColumn = 'cites_pub_id';
  } else if (columns.has('pub_id') && columns.has('cited_pub_id')) {
    citedColumn = 'cited_pub_id';
    citingColumn = 'pub_id';
  } else {
    throw new Error('Unsupported public.citation structure');
  }

  // Column names are selected exclusively from the fixed whitelist above.
  const result = await client.query(
    `WITH yearly_citations AS (
       SELECT citing.year,
         COUNT(DISTINCT (c.${citedColumn}, c.${citingColumn}))::int AS citations
       FROM public.citation c
       JOIN public.publication citing ON citing.pub_id = c.${citingColumn}
       WHERE c.${citedColumn} = ANY($1) AND citing.year IS NOT NULL
       GROUP BY citing.year
     ),
     yearly_adjusted AS (
       SELECT citing.year, SUM(isc.adjusted_citation) AS adjusted_citations
       FROM public.influential_self_citations isc
       JOIN public.publication citing ON citing.pub_id = isc.citing_pub_id
       WHERE isc.cited_pub_id = ANY($1)
         AND isc.target_author_id = $2
         AND citing.year IS NOT NULL
       GROUP BY citing.year
     )
     SELECT COALESCE(yc.year, ya.year) AS year,
       COALESCE(yc.citations, 0) AS citations,
       COALESCE(ya.adjusted_citations, 0) AS adjusted_citations
     FROM yearly_citations yc
     FULL OUTER JOIN yearly_adjusted ya ON ya.year = yc.year
     ORDER BY year`,
    [citedPublicationIds, authorId]
  );
  return result.rows;
}

async function fetchAuthorData(authorName, authorId) {
  const client = await pool.connect();
  try {
    const authorResult = await client.query(
      `SELECT author_id, author_name, career_compensation
       FROM public.author
       WHERE ($2::text IS NOT NULL AND author_id = $2)
          OR ($2::text IS NULL AND LOWER(author_name) = LOWER($1))
       LIMIT 1`,
      [(authorName || '').trim(), authorId || null]
    );
    if (!authorResult.rowCount) return null;
    const author = authorResult.rows[0];

    const result = await client.query(
      `SELECT p.pub_id, p.pub_title, p.abstract, p.year, p.total_citation, p.source,
        fc.field1_name, fc.field1_weight, fc.field2_name, fc.field2_weight,
        fc.field3_name, fc.field3_weight, acw.author_ordering_norm,
        acw.author1id, acw.author1id_weight, acw.author2id, acw.author2id_weight,
        acw.author3id, acw.author3id_weight, acw.author4id, acw.author4id_weight,
        acw.author5id, acw.author5id_weight, acw.author6id, acw.author6id_weight,
        acw.author7id, acw.author7id_weight, acw.author8id, acw.author8id_weight,
        acw.author9id, acw.author9id_weight, acw.author10id, acw.author10id_weight,
        COALESCE(apac.citing_paper_count, 0) citing_paper_count,
        COALESCE(apac.total_raw_citation, 0) raw_citations,
        COALESCE(apac.total_adjusted_citation, 0) adjusted_citations,
        COALESCE(isc.self_citation_count, 0) self_citation_count,
        COALESCE(isc.average_isc, 0) average_isc
       FROM public.publication p
       JOIN public.author_contribution_weight acw ON acw.pub_id = p.pub_id
       LEFT JOIN public.field_classification fc ON fc.pub_id = p.pub_id
       LEFT JOIN public.author_paper_adjusted_citations apac
         ON apac.cited_pub_id = p.pub_id AND apac.target_author_id = $1
       LEFT JOIN LATERAL (
         SELECT COUNT(DISTINCT citing_pub_id)::int self_citation_count, AVG(isc_value) average_isc
         FROM public.influential_self_citations
         WHERE cited_pub_id = p.pub_id AND target_author_id = $1 AND isc_value > 0
       ) isc ON TRUE
       WHERE $1 = ANY(ARRAY[acw.author1id, acw.author2id, acw.author3id, acw.author4id,
         acw.author5id, acw.author6id, acw.author7id, acw.author8id, acw.author9id, acw.author10id])
       ORDER BY p.year DESC NULLS LAST, p.total_citation DESC NULLS LAST`,
      [author.author_id]
    );

    const authorIds = [...new Set(result.rows.flatMap((row) =>
      Array.from({ length: 10 }, (_, i) => row[`author${i + 1}id`]).filter(Boolean)))];
    const names = authorIds.length
      ? await client.query('SELECT author_id, author_name FROM public.author WHERE author_id = ANY($1)', [authorIds])
      : { rows: [] };
    const nameById = new Map(names.rows.map((row) => [row.author_id, row.author_name]));

    const publications = result.rows.map((row) => {
      const authors = Array.from({ length: 10 }, (_, i) => {
        const position = i + 1;
        const id = row[`author${position}id`];
        return id ? {
          id, name: nameById.get(id) || id,
          weight: numeric(row[`author${position}id_weight`]), position,
        } : null;
      }).filter(Boolean);
      const fieldDetails = [1, 2, 3].map((i) => row[`field${i}_name`] ? {
        name: row[`field${i}_name`], weight: numeric(row[`field${i}_weight`]),
      } : null).filter(Boolean);
      return {
        id: row.pub_id, title: row.pub_title || 'Untitled publication',
        abstract: row.abstract || '', source: row.source || '',
        fields: fieldDetails.map((field) => field.name), fieldDetails, authors,
        authorContributionWeight: authors.find((item) => item.id === author.author_id)?.weight || 0,
        authorOrdering: row.author_ordering_norm || 'Unknown',
        selfCitations: Number(row.self_citation_count), averageIsc: numeric(row.average_isc),
        publishedYear: row.year, totalCitations: Number(row.total_citation || 0),
        rawCitations: numeric(row.raw_citations), adjustedCitations: numeric(row.adjusted_citations),
        citingPaperCount: Number(row.citing_paper_count),
      };
    });

    const annualCitationImpact = await fetchAnnualCitationImpact(
      client,
      publications.map((publication) => publication.id),
      author.author_id
    );

    const scoreResult = await client.query(
      `SELECT first_publication_year, as_of_year, career_time_years, career_factor,
        included_publication_count, total_cites_score, calculation_complete, calculated_at
       FROM public.author_total_cites WHERE author_id = $1`, [author.author_id]
    );
    const score = scoreResult.rows[0];
    return {
      authorId: author.author_id, author: author.author_name,
      totalPublications: publications.length,
      totalCitations: publications.reduce((sum, item) => sum + item.totalCitations, 0),
      totalSelfCitations: publications.reduce((sum, item) => sum + item.selfCitations, 0),
      totalAdjustedCitations: publications.reduce((sum, item) => sum + item.adjustedCitations, 0),
      nmIndex: publications.filter((item) => item.totalCitations >= 10).length,
      hIndex: hIndex(publications.map((item) => item.totalCitations)),
      cScore: score ? numeric(score.total_cites_score) : 0,
      careerCompensation: numeric(author.career_compensation),
      scoreDetails: score ? {
        firstPublicationYear: score.first_publication_year, asOfYear: score.as_of_year,
        careerTimeYears: score.career_time_years, careerFactor: numeric(score.career_factor),
        includedPublicationCount: score.included_publication_count,
        calculationComplete: score.calculation_complete, calculatedAt: score.calculated_at,
      } : null,
      trendData: trendData(publications, annualCitationImpact), publications,
    };
  } finally {
    client.release();
  }
}

router.get('/', async (req, res) => {
  try {
    if (!req.query.author?.trim() && !req.query.authorId?.trim()) {
      return res.status(400).json({ message: 'Author name or ID is required' });
    }
    const data = await fetchAuthorData(req.query.author, req.query.authorId);
    if (!data) return res.status(404).json({ message: 'Author not found in database' });
    return res.json(data);
  } catch (error) {
    console.error('Author search failed:', error);
    const unavailable = ['ECONNREFUSED', 'ETIMEDOUT', 'ECONNRESET'].includes(error.code)
      || /timeout|connection terminated/i.test(error.message);
    return res.status(unavailable ? 503 : 500).json({
      message: unavailable
        ? 'PostgreSQL is currently unavailable. Please try again shortly.'
        : 'Unable to read author metrics from PostgreSQL',
    });
  }
});

module.exports = router;
