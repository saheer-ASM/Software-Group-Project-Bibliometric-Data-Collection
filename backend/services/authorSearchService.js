const authorRepo  = require('../repositories/authorRepository');
const metricCalc  = require('./metricCalculatorService');

async function searchByName(name) {
  const authors = await authorRepo.findByName(name);
  return authors;
}

async function getAuthorDetails(authorId, filters = {}) {
  const author = await authorRepo.findById(authorId);
  if (!author) return null;

  const publications = await authorRepo.getPublications(authorId, filters);

  // Recalculate metrics live so they reflect any active filters
  const metrics = metricCalc.calculateAll(publications);

  // Persist fresh metrics (unfiltered) only when no filter is active
  if (!filters.field && !filters.year) {
    await authorRepo.upsertMetrics(authorId, metrics);
  }

  // Attach co-authors to each publication
  const enriched = await Promise.all(
    publications.map(async (pub) => {
      const coAuthors = await authorRepo.getCoAuthors(authorId, pub.publication_id);
      return { ...pub, coAuthors };
    })
  );

  return {
    author: {
      ...author,
      hIndex:             metrics.hIndex,
      cIndex:             metrics.cIndex,
      nmIndex:            metrics.nmIndex,
      totalCitations:     metrics.totalCitations,
      totalSelfCitations: metrics.totalSelfCitations,
      totalPublications:  metrics.totalPublications,
    },
    publications: enriched,
  };
}

module.exports = { searchByName, getAuthorDetails };
