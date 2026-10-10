const express = require('express');
const pool = require('../config/database');

const router = express.Router();
const numeric = (value) => (Number.isFinite(Number(value)) ? Number(value) : 0);

// Publication paging. The cap is enforced server-side so a client can never ask
// for an unbounded page.
const DEFAULT_PUBLICATION_LIMIT = 20;
const MAX_PUBLICATION_LIMIT = 50;

// Matches an author against the ten contribution-weight author slots.
const AUTHOR_MATCH_SQL = `$1 = ANY(ARRAY[acw.author1id, acw.author2id, acw.author3id, acw.author4id,
  acw.author5id, acw.author6id, acw.author7id, acw.author8id, acw.author9id, acw.author10id])`;

function parsePaging(query) {
  const rawPage = Number.parseInt(query.page, 10);
  const rawLimit = Number.parseInt(query.limit, 10);
  const page = Number.isFinite(rawPage) && rawPage > 0 ? rawPage : 1;
  const limit = Number.isFinite(rawLimit) && rawLimit > 0
    ? Math.min(rawLimit, MAX_PUBLICATION_LIMIT)
    : DEFAULT_PUBLICATION_LIMIT;
  return { page, limit, offset: (page - 1) * limit };
}

function pagination(page, limit, total) {
  const totalPages = total > 0 ? Math.ceil(total / limit) : 0;
  return {
    page, limit, total, totalPages,
    hasNextPage: page < totalPages,
    hasPreviousPage: page > 1,
  };
}

// Takes per-year counts straight from SQL. Previously this counted the
// publications array, which is why every publication had to be loaded just to
// draw the trend chart -- the reason the endpoint could not be paged.
function trendData(publicationsByYear = [], citationImpactByYear = []) {
  const years = new Map();
  publicationsByYear.forEach((row) => {
    const key = row.year === null || row.year === undefined ? 'Unknown' : row.year;
    years.set(key, {
      name: String(key), publications: Number(row.publications) || 0,
      citations: 0, adjustedCitations: 0,
    });
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

async function fetchAnnualCitationImpact(client, authorId) {

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
    `WITH author_pubs AS (
       SELECT p.pub_id
       FROM public.publication p
       JOIN public.author_contribution_weight acw ON acw.pub_id = p.pub_id
       WHERE ${AUTHOR_MATCH_SQL}
     ),
     yearly_citations AS (
       SELECT citing.year,
         COUNT(DISTINCT (c.${citedColumn}, c.${citingColumn}))::int AS citations
       FROM public.citation c
       JOIN public.publication citing ON citing.pub_id = c.${citingColumn}
       WHERE c.${citedColumn} IN (SELECT pub_id FROM author_pubs) AND citing.year IS NOT NULL
       GROUP BY citing.year
     ),
     yearly_adjusted AS (
       SELECT citing.year, SUM(isc.adjusted_citation) AS adjusted_citations
       FROM public.influential_self_citations isc
       JOIN public.publication citing ON citing.pub_id = isc.citing_pub_id
       WHERE isc.cited_pub_id IN (SELECT pub_id FROM author_pubs)
         AND isc.target_author_id = $1
         AND citing.year IS NOT NULL
       GROUP BY citing.year
     )
     SELECT COALESCE(yc.year, ya.year) AS year,
       COALESCE(yc.citations, 0) AS citations,
       COALESCE(ya.adjusted_citations, 0) AS adjusted_citations
     FROM yearly_citations yc
     FULL OUTER JOIN yearly_adjusted ya ON ya.year = yc.year
     ORDER BY year`,
    [authorId]
  );
  return result.rows;
}


// --------------------------------------------------------------------------
// Publication filters, translated to SQL.
//
// These mirror frontend/src/services/publicationFilters.js one-for-one. They
// have to run in the database: with paging the browser only holds the current
// page, so filtering there would hide matches that live on later pages.
// --------------------------------------------------------------------------

// Which of the ten author slots this author occupies, and the weight recorded
// against that slot. Used by the "contribution" filter.
const AUTHOR_POSITION_SQL = `CASE ${
  Array.from({ length: 10 }, (_, i) => `WHEN acw.author${i + 1}id = $1 THEN ${i + 1}`).join(' ')
} END`;

const AUTHOR_WEIGHT_SQL = `CASE ${
  Array.from({ length: 10 }, (_, i) => `WHEN acw.author${i + 1}id = $1 THEN acw.author${i + 1}id_weight`).join(' ')
} END`;

// filterPublications() treats a weight <= 1 as a proportion and scales it.
const AUTHOR_PERCENT_SQL = `(CASE WHEN COALESCE((${AUTHOR_WEIGHT_SQL})::numeric, 0) <= 1
  THEN COALESCE((${AUTHOR_WEIGHT_SQL})::numeric, 0) * 100
  ELSE COALESCE((${AUTHOR_WEIGHT_SQL})::numeric, 0) END)`;

const SELF_CITATIONS_SQL = 'COALESCE(isc.self_citation_count, 0)';
const TOTAL_CITATIONS_SQL = 'COALESCE(p.total_citation, 0)';
const ADJUSTED_CITATIONS_SQL = 'COALESCE(apac.total_adjusted_citation, 0)';

// Shared FROM/JOIN used by the page query, the count query and the facet
// queries, so a row can never match one and not the other.
const PUBLICATION_FROM_SQL = `
  FROM public.publication p
  JOIN public.author_contribution_weight acw ON acw.pub_id = p.pub_id
  LEFT JOIN public.field_classification fc ON fc.pub_id = p.pub_id
  LEFT JOIN public.author_paper_adjusted_citations apac
    ON apac.cited_pub_id = p.pub_id AND apac.target_author_id = $1
  LEFT JOIN LATERAL (
    SELECT COUNT(DISTINCT citing_pub_id)::int self_citation_count, AVG(isc_value) average_isc
    FROM public.influential_self_citations
    WHERE cited_pub_id = p.pub_id AND target_author_id = $1 AND isc_value > 0
  ) isc ON TRUE`;

const CITATION_TYPES = new Set(['external', 'self', 'adjusted']);
const IMPACT_LEVELS = new Set(['high', 'medium', 'low', 'uncited']);
const CONTRIBUTIONS = new Set(['primary', 'major', 'minor', 'coauthor']);

/**
 * Builds the WHERE clause for a filter set. $1 is always the author id;
 * further values are appended to `params` and referenced positionally, so
 * every value is bound, never interpolated.
 */
// Every pub_id in the database is an OpenAlex work id: "W" followed by digits.
const PUBLICATION_ID_PATTERN = /^W\d{1,20}$/;

function buildPublicationFilters(query, params) {
  const clauses = [AUTHOR_MATCH_SQL];
  const add = (value) => { params.push(value); return `$${params.length}`; };

  // One specific publication, still in this author's context: the card's
  // author-specific figures (contribution, self and adjusted citations) need
  // the author, and the result has exactly the shape of a normal page.
  const pubId = (query.pubId || '').trim();
  if (PUBLICATION_ID_PATTERN.test(pubId)) clauses.push(`p.pub_id = ${add(pubId)}`);

  const title = (query.query || '').trim();
  if (title) clauses.push(`p.pub_title ILIKE ${add(`%${title}%`)}`);

  const field = (query.field || '').trim();
  if (field) {
    const placeholder = add(field);
    clauses.push(`${placeholder} IN (fc.field1_name, fc.field2_name, fc.field3_name)`);
  }

  // The UI filters on an inclusive year range and drops publications with no
  // year, which `p.year BETWEEN` reproduces (NULL fails the comparison).
  const yearFrom = Number.parseInt(query.yearFrom, 10);
  const yearTo = Number.parseInt(query.yearTo, 10);
  if (Number.isFinite(yearFrom)) clauses.push(`p.year >= ${add(yearFrom)}`);
  if (Number.isFinite(yearTo)) clauses.push(`p.year <= ${add(yearTo)}`);

  const citationType = (query.citationType || '').trim();
  if (CITATION_TYPES.has(citationType)) {
    if (citationType === 'external') clauses.push(`${TOTAL_CITATIONS_SQL} - ${SELF_CITATIONS_SQL} > 0`);
    if (citationType === 'self') clauses.push(`${SELF_CITATIONS_SQL} > 0`);
    if (citationType === 'adjusted') clauses.push(`${ADJUSTED_CITATIONS_SQL} > 0`);
  }

  // impactLevel() buckets the citation count; `view` picks which count.
  const impact = (query.impact || '').trim();
  if (IMPACT_LEVELS.has(impact)) {
    const value = query.view === 'adjusted' ? ADJUSTED_CITATIONS_SQL : TOTAL_CITATIONS_SQL;
    if (impact === 'high') clauses.push(`${value} >= 10`);
    if (impact === 'medium') clauses.push(`${value} >= 5 AND ${value} < 10`);
    if (impact === 'low') clauses.push(`${value} > 0 AND ${value} < 5`);
    if (impact === 'uncited') clauses.push(`${value} <= 0`);
  }

  const contribution = (query.contribution || '').trim();
  if (CONTRIBUTIONS.has(contribution)) {
    if (contribution === 'primary') clauses.push(`(${AUTHOR_POSITION_SQL}) = 1`);
    if (contribution === 'coauthor') clauses.push(`(${AUTHOR_POSITION_SQL}) > 1`);
    if (contribution === 'major') clauses.push(`${AUTHOR_PERCENT_SQL} >= 25`);
    if (contribution === 'minor') clauses.push(`${AUTHOR_PERCENT_SQL} > 0 AND ${AUTHOR_PERCENT_SQL} < 25`);
  }

  return clauses.join('\n     AND ');
}

// Default ordering, unchanged from the original query. pub_id is the
// tiebreaker: without it rows tied on year+citations could shuffle between
// pages, so a publication could appear twice or not at all.
const PUBLICATION_ORDER_SQL =
  'ORDER BY p.year DESC NULLS LAST, p.total_citation DESC NULLS LAST, p.pub_id DESC';

// One page of an author's publications. LIMIT/OFFSET are applied by the
// database -- nothing fetches the whole set and slices it afterwards.
async function fetchPublicationsPage(client, authorId, { limit, offset, filters = {} }) {
  const params = [authorId];
  const where = buildPublicationFilters(filters, params);
  // Bound after the filters so the placeholder numbers line up with params.
  const limitAt = "$" + params.push(limit);
  const offsetAt = "$" + params.push(offset);
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
     ${PUBLICATION_FROM_SQL}
     WHERE ${where}
     ${PUBLICATION_ORDER_SQL}
     LIMIT ${limitAt} OFFSET ${offsetAt}`,
    params
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
      authorContributionWeight: authors.find((item) => item.id === authorId)?.weight || 0,
      authorOrdering: row.author_ordering_norm || 'Unknown',
      selfCitations: Number(row.self_citation_count), averageIsc: numeric(row.average_isc),
      publishedYear: row.year, totalCitations: Number(row.total_citation || 0),
      rawCitations: numeric(row.raw_citations), adjustedCitations: numeric(row.adjusted_citations),
      citingPaperCount: Number(row.citing_paper_count),
    };
  });

  return publications;
}

// Total used for the paging metadata. Same joins as the page query above so
// the count and the pages can never disagree.
async function countAuthorPublications(client, authorId, filters = {}) {
  const params = [authorId];
  const where = buildPublicationFilters(filters, params);
  const result = await client.query(
    `SELECT COUNT(*)::int AS total
     ${PUBLICATION_FROM_SQL}
     WHERE ${where}`,
    params
  );
  return Number(result.rows[0]?.total || 0);
}

// Per-year publication counts for the trend chart, aggregated in SQL.
async function fetchPublicationsByYear(client, authorId) {
  const result = await client.query(
    `SELECT p.year, COUNT(*)::int AS publications
     FROM public.publication p
     JOIN public.author_contribution_weight acw ON acw.pub_id = p.pub_id
     WHERE ${AUTHOR_MATCH_SQL}
     GROUP BY p.year
     ORDER BY p.year`,
    [authorId]
  );
  return result.rows;
}

// Filter dropdown options. These must come from the author's whole corpus,
// not the loaded page: deriving them in the browser from one page of 20 would
// hide every year and field that happens to fall on a later page.
async function fetchPublicationFacets(client, authorId) {
  const result = await client.query(
    `WITH author_pubs AS (
       SELECT p.year, fc.field1_name, fc.field2_name, fc.field3_name
       FROM public.publication p
       JOIN public.author_contribution_weight acw ON acw.pub_id = p.pub_id
       LEFT JOIN public.field_classification fc ON fc.pub_id = p.pub_id
       WHERE ${AUTHOR_MATCH_SQL}
     )
     SELECT
       (SELECT COALESCE(ARRAY_AGG(DISTINCT year ORDER BY year), '{}'::int[])
          FROM author_pubs WHERE year IS NOT NULL) AS years,
       (SELECT COALESCE(ARRAY_AGG(DISTINCT name ORDER BY name), '{}'::text[])
          FROM author_pubs,
               LATERAL (VALUES (field1_name), (field2_name), (field3_name)) AS f(name)
          WHERE name IS NOT NULL AND name <> '') AS fields`,
    [authorId]
  );
  const row = result.rows[0] || {};
  return {
    years: (row.years || []).map(Number).filter(Number.isInteger),
    fields: row.fields || [],
  };
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

    const paging = { limit: DEFAULT_PUBLICATION_LIMIT, offset: 0 };
    const [publications, publicationTotal, publicationsByYear, publicationFacets] = await Promise.all([
      fetchPublicationsPage(client, author.author_id, paging),
      countAuthorPublications(client, author.author_id),
      fetchPublicationsByYear(client, author.author_id),
      fetchPublicationFacets(client, author.author_id),
    ]);

    const annualCitationImpact = await fetchAnnualCitationImpact(client, author.author_id);

    const metricsResult = await client.query(
      `WITH author_publications AS (
         SELECT p.pub_id, COALESCE(p.total_citation, 0)::numeric AS total_citation
         FROM public.publication p
         JOIN public.author_contribution_weight acw ON acw.pub_id = p.pub_id
         WHERE $1 = ANY(ARRAY[acw.author1id, acw.author2id, acw.author3id, acw.author4id,
           acw.author5id, acw.author6id, acw.author7id, acw.author8id, acw.author9id, acw.author10id])
       ),
       ranked_publications AS (
         SELECT total_citation,
           ROW_NUMBER() OVER (ORDER BY total_citation DESC)::int AS citation_rank
         FROM author_publications
       )
       SELECT
         (SELECT COUNT(*)::int FROM author_publications) AS total_publications,
         (SELECT COALESCE(SUM(total_citation), 0) FROM author_publications) AS total_citations,
         (SELECT COALESCE(SUM(apac.total_adjusted_citation), 0)
            FROM author_publications ap
            LEFT JOIN public.author_paper_adjusted_citations apac
              ON apac.cited_pub_id = ap.pub_id AND apac.target_author_id = $1
         ) AS total_adjusted_citations,
         (SELECT COALESCE(SUM(self_citation_count), 0)
            FROM author_publications ap
            LEFT JOIN LATERAL (
              SELECT COUNT(DISTINCT citing_pub_id)::int AS self_citation_count
              FROM public.influential_self_citations
              WHERE cited_pub_id = ap.pub_id AND target_author_id = $1 AND isc_value > 0
            ) isc ON TRUE
         ) AS total_self_citations,
         (SELECT COALESCE(MAX(citation_rank), 0)
            FROM ranked_publications
            WHERE total_citation >= citation_rank
         ) AS h_index,
         (SELECT nm_index FROM public.author_nm_index WHERE author_id = $1) AS nm_index`,
      [author.author_id]
    );
    const metrics = metricsResult.rows[0];

    const scoreResult = await client.query(
      `SELECT first_publication_year, as_of_year, career_time_years, career_factor,
        included_publication_count, total_cites_score, calculation_complete, calculated_at
       FROM public.author_total_cites WHERE author_id = $1`, [author.author_id]
    );
    const score = scoreResult.rows[0];
    return {
      authorId: author.author_id, author: author.author_name,
      totalPublications: Number(metrics.total_publications),
      totalCitations: numeric(metrics.total_citations),
      totalSelfCitations: numeric(metrics.total_self_citations),
      totalAdjustedCitations: numeric(metrics.total_adjusted_citations),
      nmIndex: numeric(metrics.nm_index),
      hIndex: Number(metrics.h_index),
      cScore: score ? numeric(score.total_cites_score) : 0,
      careerCompensation: numeric(author.career_compensation),
      scoreDetails: score ? {
        firstPublicationYear: score.first_publication_year, asOfYear: score.as_of_year,
        careerTimeYears: score.career_time_years, careerFactor: numeric(score.career_factor),
        includedPublicationCount: score.included_publication_count,
        calculationComplete: score.calculation_complete, calculatedAt: score.calculated_at,
      } : null,
      trendData: trendData(publicationsByYear, annualCitationImpact),
      publications,
      publicationsPagination: pagination(1, DEFAULT_PUBLICATION_LIMIT, publicationTotal),
      publicationFacets,
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

// Paginated publications for an author. The Data Explorer calls this for
// "Load More"; page 1 already arrives with the author payload from GET /.
// Auth posture deliberately matches GET / on this router -- changing it here
// would break the Data Explorer, which calls both with the same credentials.
router.get('/publications', async (req, res) => {
  const authorId = (req.query.authorId || '').trim();
  if (!authorId) {
    return res.status(400).json({ message: 'authorId is required' });
  }
  // A malformed pubId must fail loudly: ignoring it would quietly return the
  // author's first page instead of the one publication that was asked for.
  if (req.query.pubId !== undefined && !PUBLICATION_ID_PATTERN.test(String(req.query.pubId).trim())) {
    return res.status(400).json({ message: 'pubId must be a publication id such as W1234567' });
  }

  const { page, limit, offset } = parsePaging(req.query);
  const client = await pool.connect();
  try {
    const [publications, total] = await Promise.all([
      fetchPublicationsPage(client, authorId, { limit, offset, filters: req.query }),
      countAuthorPublications(client, authorId, req.query),
    ]);
    return res.json({ publications, pagination: pagination(page, limit, total) });
  } catch (error) {
    console.error('Publication page failed:', error);
    const unavailable = ['ECONNREFUSED', 'ETIMEDOUT', 'ECONNRESET'].includes(error.code)
      || /timeout|connection terminated/i.test(error.message);
    return res.status(unavailable ? 503 : 500).json({
      message: unavailable
        ? 'PostgreSQL is currently unavailable. Please try again shortly.'
        : 'Unable to read publications from PostgreSQL',
    });
  } finally {
    client.release();
  }
});

module.exports = router;
