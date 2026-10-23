const express = require('express');
const pool = require('../config/database');
const { parseAuthorQuery, lowerFunctionFor } = require('../services/authorQuery');

const router = express.Router();
const numeric = (value) => (Number.isFinite(Number(value)) ? Number(value) : 0);

// SQLite keeps booleans as 0/1 and CURRENT_TIMESTAMP as UTC text
// ("2026-10-16 14:57:08"); the API still returns the boolean and the ISO
// timestamp that PostgreSQL's boolean and timestamptz columns produced.
const isoTimestamp = (value) => (
  /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(value) ? `${value.replace(' ', 'T')}.000Z` : value
);

// Publication paging. The cap is enforced server-side so a client can never ask
// for an unbounded page.
const DEFAULT_PUBLICATION_LIMIT = 20;
const MAX_PUBLICATION_LIMIT = 50;

// Matches an author against the ten contribution-weight author slots. Those
// columns have no index, so this scans all of author_contribution_weight
// (about 3M rows). It runs once per request, in fetchAuthorPublicationIds;
// every other query reuses that list through AUTHOR_PUBLICATIONS_SQL.
const AUTHOR_MATCH_SQL = `?1 IN (acw.author1id, acw.author2id, acw.author3id, acw.author4id,
  acw.author5id, acw.author6id, acw.author7id, acw.author8id, acw.author9id, acw.author10id)`;

// The author's publications: ?2 is the JSON array from
// fetchAuthorPublicationIds. pub_id is the primary key, so this is an index
// lookup per publication instead of another full scan.
const AUTHOR_PUBLICATIONS_SQL = 'p.pub_id IN (SELECT value FROM json_each(?2))';

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

// The columns a table has in this database, so a query can adapt to them.
async function tableColumns(client, table) {
  const result = await client.query('SELECT name FROM pragma_table_info(?1)', [table]);
  return new Set(result.rows.map((row) => row.name));
}

// Every publication of the author, as the JSON array AUTHOR_PUBLICATIONS_SQL
// reads.
async function fetchAuthorPublicationIds(client, authorId) {
  const result = await client.query(
    `SELECT p.pub_id
     FROM author_contribution_weight acw
     JOIN publication p ON p.pub_id = acw.pub_id
     WHERE ${AUTHOR_MATCH_SQL}`,
    [authorId]
  );
  return JSON.stringify(result.rows.map((row) => row.pub_id));
}

async function fetchAnnualCitationImpact(client, authorId, publicationIds) {

  const columns = await tableColumns(client, 'citation');
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
    throw new Error('Unsupported citation table structure');
  }

  // Column names are selected exclusively from the fixed whitelist above.
  const result = await client.query(
    `WITH yearly_citations AS (
       SELECT citing.year,
         COUNT(DISTINCT c.${citedColumn} || '|' || c.${citingColumn}) AS citations
       FROM citation c
       JOIN publication citing ON citing.pub_id = c.${citingColumn}
       WHERE c.${citedColumn} IN (SELECT value FROM json_each(?2)) AND citing.year IS NOT NULL
       GROUP BY citing.year
     ),
     yearly_adjusted AS (
       SELECT citing.year, SUM(isc.adjusted_citation) AS adjusted_citations
       FROM influential_self_citations isc
       JOIN publication citing ON citing.pub_id = isc.citing_pub_id
       WHERE isc.cited_pub_id IN (SELECT value FROM json_each(?2))
         AND isc.target_author_id = ?1
         AND citing.year IS NOT NULL
       GROUP BY citing.year
     )
     SELECT COALESCE(yc.year, ya.year) AS year,
       COALESCE(yc.citations, 0) AS citations,
       COALESCE(ya.adjusted_citations, 0) AS adjusted_citations
     FROM yearly_citations yc
     FULL OUTER JOIN yearly_adjusted ya ON ya.year = yc.year
     ORDER BY year`,
    [authorId, publicationIds]
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
  Array.from({ length: 10 }, (_, i) => `WHEN acw.author${i + 1}id = ?1 THEN ${i + 1}`).join(' ')
} END`;

const AUTHOR_WEIGHT_SQL = `CASE ${
  Array.from({ length: 10 }, (_, i) => `WHEN acw.author${i + 1}id = ?1 THEN acw.author${i + 1}id_weight`).join(' ')
} END`;

// filterPublications() treats a weight <= 1 as a proportion and scales it.
const AUTHOR_PERCENT_SQL = `(CASE WHEN COALESCE(CAST((${AUTHOR_WEIGHT_SQL}) AS REAL), 0) <= 1
  THEN COALESCE(CAST((${AUTHOR_WEIGHT_SQL}) AS REAL), 0) * 100
  ELSE COALESCE(CAST((${AUTHOR_WEIGHT_SQL}) AS REAL), 0) END)`;

const SELF_CITATIONS_SQL = 'COALESCE(isc.self_citation_count, 0)';
const TOTAL_CITATIONS_SQL = 'COALESCE(p.total_citation, 0)';
const ADJUSTED_CITATIONS_SQL = 'COALESCE(apac.total_adjusted_citation, 0)';

// Shared FROM/JOIN used by the page query and the count query, so a row can
// never match one and not the other. SQLite has no LATERAL join, so the
// influential self-citations of the author's publications are aggregated
// once in the isc subquery and joined per publication.
const PUBLICATION_FROM_SQL = `
  FROM publication p
  JOIN author_contribution_weight acw ON acw.pub_id = p.pub_id
  LEFT JOIN field_classification fc ON fc.pub_id = p.pub_id
  LEFT JOIN author_paper_adjusted_citations apac
    ON apac.cited_pub_id = p.pub_id AND apac.target_author_id = ?1
  LEFT JOIN (
    SELECT cited_pub_id, COUNT(DISTINCT citing_pub_id) AS self_citation_count,
      AVG(isc_value) AS average_isc
    FROM influential_self_citations
    WHERE cited_pub_id IN (SELECT value FROM json_each(?2))
      AND target_author_id = ?1 AND isc_value > 0
    GROUP BY cited_pub_id
  ) isc ON isc.cited_pub_id = p.pub_id`;

const CITATION_TYPES = new Set(['external', 'self', 'adjusted']);
const IMPACT_LEVELS = new Set(['high', 'medium', 'low', 'uncited']);
const CONTRIBUTIONS = new Set(['primary', 'major', 'minor', 'coauthor']);

/**
 * Builds the WHERE clause for a filter set. ?1 is always the author id and ?2
 * the author's publication list; further values are appended to `params` and
 * referenced by number, so every value is bound, never interpolated.
 */
// Every pub_id in the database is an OpenAlex work id: "W" followed by digits.
const PUBLICATION_ID_PATTERN = /^W\d{1,20}$/;

function buildPublicationFilters(query, params) {
  const clauses = [AUTHOR_PUBLICATIONS_SQL];
  const add = (value) => { params.push(value); return `?${params.length}`; };

  // One specific publication, still in this author's context: the card's
  // author-specific figures (contribution, self and adjusted citations) need
  // the author, and the result has exactly the shape of a normal page.
  const pubId = (query.pubId || '').trim();
  if (PUBLICATION_ID_PATTERN.test(pubId)) clauses.push(`p.pub_id = ${add(pubId)}`);

  // SQLite's LIKE ignores case for ASCII letters, as PostgreSQL's ILIKE did.
  const title = (query.query || '').trim();
  if (title) clauses.push(`p.pub_title LIKE ${add(`%${title}%`)}`);

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
async function fetchPublicationsPage(client, authorId, publicationIds, { limit, offset, filters = {} }) {
  const params = [authorId, publicationIds];
  const where = buildPublicationFilters(filters, params);
  // Bound after the filters so the placeholder numbers line up with params.
  const limitAt = "?" + params.push(limit);
  const offsetAt = "?" + params.push(offset);
  // publication.source (the publisher) was in the cloud database; the local
  // one does not have it yet, and the card simply omits an empty source.
  const source = (await tableColumns(client, 'publication')).has('source') ? 'p.source' : 'NULL AS source';
  const result = await client.query(
    `SELECT p.pub_id, p.pub_title, p.abstract, p.year, p.total_citation, ${source},
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
    ? await client.query(
      'SELECT author_id, author_name FROM author WHERE author_id IN (SELECT value FROM json_each(?1))',
      [JSON.stringify(authorIds)])
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
async function countAuthorPublications(client, authorId, publicationIds, filters = {}) {
  const params = [authorId, publicationIds];
  const where = buildPublicationFilters(filters, params);
  const result = await client.query(
    `SELECT COUNT(*) AS total
     ${PUBLICATION_FROM_SQL}
     WHERE ${where}`,
    params
  );
  return Number(result.rows[0]?.total || 0);
}

// Per-year publication counts for the trend chart, aggregated in SQL.
async function fetchPublicationsByYear(client, authorId, publicationIds) {
  const result = await client.query(
    `SELECT p.year, COUNT(*) AS publications
     FROM publication p
     WHERE ${AUTHOR_PUBLICATIONS_SQL}
     GROUP BY p.year
     ORDER BY p.year NULLS LAST`,
    [authorId, publicationIds]
  );
  return result.rows;
}

// Filter dropdown options. These must come from the author's whole corpus,
// not the loaded page: deriving them in the browser from one page of 20 would
// hide every year and field that happens to fall on a later page.
async function fetchPublicationFacets(client, authorId, publicationIds) {
  const result = await client.query(
    `WITH author_pubs AS (
       SELECT p.year, fc.field1_name, fc.field2_name, fc.field3_name
       FROM publication p
       LEFT JOIN field_classification fc ON fc.pub_id = p.pub_id
       WHERE ${AUTHOR_PUBLICATIONS_SQL}
     )
     SELECT
       (SELECT json_group_array(DISTINCT year ORDER BY year)
          FROM author_pubs WHERE year IS NOT NULL) AS years,
       (SELECT json_group_array(DISTINCT name ORDER BY name)
          FROM (SELECT field1_name AS name FROM author_pubs
                UNION ALL SELECT field2_name FROM author_pubs
                UNION ALL SELECT field3_name FROM author_pubs)
          WHERE name IS NOT NULL AND name <> '') AS fields`,
    [authorId, publicationIds]
  );
  const row = result.rows[0] || {};
  return {
    years: JSON.parse(row.years || '[]').map(Number).filter(Number.isInteger),
    fields: JSON.parse(row.fields || '[]'),
  };
}

async function fetchAuthorData(authorName, authorId) {
  const client = await pool.connect();
  try {
    // Two separate lookups: SQLite cannot use the primary key for an OR that
    // also covers the name match, and would scan every author for an id.
    const name = (authorName || '').trim();
    const lower = lowerFunctionFor(name);
    const authorResult = authorId
      ? await client.query(
        `SELECT author_id, author_name, career_compensation
         FROM author WHERE author_id = ?1 LIMIT 1`,
        [authorId])
      : await client.query(
        `SELECT author_id, author_name, career_compensation
         FROM author WHERE ${lower}(author_name) = ${lower}(?1) LIMIT 1`,
        [name]);
    if (!authorResult.rowCount) return null;
    const author = authorResult.rows[0];
    const publicationIds = await fetchAuthorPublicationIds(client, author.author_id);

    const paging = { limit: DEFAULT_PUBLICATION_LIMIT, offset: 0 };
    const [publications, publicationTotal, publicationsByYear, publicationFacets] = await Promise.all([
      fetchPublicationsPage(client, author.author_id, publicationIds, paging),
      countAuthorPublications(client, author.author_id, publicationIds),
      fetchPublicationsByYear(client, author.author_id, publicationIds),
      fetchPublicationFacets(client, author.author_id, publicationIds),
    ]);

    const annualCitationImpact = await fetchAnnualCitationImpact(client, author.author_id, publicationIds);

    const metricsResult = await client.query(
      `WITH author_publications AS (
         SELECT p.pub_id, COALESCE(p.total_citation, 0) AS total_citation
         FROM publication p
         WHERE ${AUTHOR_PUBLICATIONS_SQL}
       ),
       ranked_publications AS (
         SELECT total_citation,
           ROW_NUMBER() OVER (ORDER BY total_citation DESC) AS citation_rank
         FROM author_publications
       )
       SELECT
         (SELECT COUNT(*) FROM author_publications) AS total_publications,
         (SELECT COALESCE(SUM(total_citation), 0) FROM author_publications) AS total_citations,
         (SELECT COALESCE(SUM(apac.total_adjusted_citation), 0)
            FROM author_publications ap
            LEFT JOIN author_paper_adjusted_citations apac
              ON apac.cited_pub_id = ap.pub_id AND apac.target_author_id = ?1
         ) AS total_adjusted_citations,
         (SELECT COALESCE(SUM((
              SELECT COUNT(DISTINCT citing_pub_id)
              FROM influential_self_citations
              WHERE cited_pub_id = ap.pub_id AND target_author_id = ?1 AND isc_value > 0
            )), 0)
            FROM author_publications ap
         ) AS total_self_citations,
         (SELECT COALESCE(MAX(citation_rank), 0)
            FROM ranked_publications
            WHERE total_citation >= citation_rank
         ) AS h_index,
         (SELECT nm_index FROM author_nm_index WHERE author_id = ?1) AS nm_index`,
      [author.author_id, publicationIds]
    );
    const metrics = metricsResult.rows[0];

    const scoreResult = await client.query(
      `SELECT first_publication_year, as_of_year, career_time_years, career_factor,
        included_publication_count, total_cites_score, calculation_complete, calculated_at
       FROM author_total_cites WHERE author_id = ?1`, [author.author_id]
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
        calculationComplete: Boolean(score.calculation_complete),
        calculatedAt: isoTimestamp(score.calculated_at),
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
    const authorId = typeof req.query.authorId === 'string' ? req.query.authorId.trim() : '';
    // With an id the name is only a label, so it may be short -- but never
    // oversized. Without one, the name is what is looked up: at least 2
    // characters, checked here so a short name never reaches the database.
    if (!authorId && typeof req.query.author !== 'string') {
      return res.status(400).json({ message: 'Author name or ID is required' });
    }
    const name = parseAuthorQuery(req.query.author, { required: !authorId });
    if (name.error) return res.status(400).json({ message: name.error });
    const data = await fetchAuthorData(name.value, authorId || undefined);
    if (!data) return res.status(404).json({ message: 'Author not found in database' });
    return res.json(data);
  } catch (error) {
    console.error('Author search failed:', error);
    const unavailable = pool.isUnavailable(error);
    return res.status(unavailable ? 503 : 500).json({
      message: unavailable
        ? 'The database is currently unavailable. Please try again shortly.'
        : 'Unable to read author metrics from the database',
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
    const publicationIds = await fetchAuthorPublicationIds(client, authorId);
    const [publications, total] = await Promise.all([
      fetchPublicationsPage(client, authorId, publicationIds, { limit, offset, filters: req.query }),
      countAuthorPublications(client, authorId, publicationIds, req.query),
    ]);
    return res.json({ publications, pagination: pagination(page, limit, total) });
  } catch (error) {
    console.error('Publication page failed:', error);
    const unavailable = pool.isUnavailable(error);
    return res.status(unavailable ? 503 : 500).json({
      message: unavailable
        ? 'The database is currently unavailable. Please try again shortly.'
        : 'Unable to read publications from the database',
    });
  } finally {
    client.release();
  }
});

module.exports = router;
