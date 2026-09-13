/**
 * H-Index: largest h such that h papers each have >= h citations.
 */
function calculateHIndex(publications) {
  const sorted = publications
    .map((p) => parseInt(p.total_citations, 10))
    .sort((a, b) => b - a);

  let h = 0;
  for (let i = 0; i < sorted.length; i++) {
    if (sorted[i] >= i + 1) h = i + 1;
    else break;
  }
  return h;
}

/**
 * C-Index (C-Score): citation-weighted index that accounts for self-citations.
 * Formula: C = total_citations - total_self_citations
 */
function calculateCIndex(publications) {
  const totalCitations     = publications.reduce((s, p) => s + parseInt(p.total_citations, 10), 0);
  const totalSelfCitations = publications.reduce((s, p) => s + parseInt(p.self_citations, 10), 0);
  return Math.max(0, totalCitations - totalSelfCitations);
}

/**
 * Nm-Index: normalized metric relative to total publications.
 * Formula: Nm = H² / total_publications  (Hirsch's own suggestion for comparing researchers)
 */
function calculateNmIndex(hIndex, totalPublications) {
  if (totalPublications === 0) return 0;
  return parseFloat((hIndex ** 2 / totalPublications).toFixed(4));
}

function calculateAll(publications) {
  const totalPublications   = publications.length;
  const totalCitations      = publications.reduce((s, p) => s + parseInt(p.total_citations, 10), 0);
  const totalSelfCitations  = publications.reduce((s, p) => s + parseInt(p.self_citations, 10), 0);

  const hIndex  = calculateHIndex(publications);
  const cIndex  = calculateCIndex(publications);
  const nmIndex = calculateNmIndex(hIndex, totalPublications);

  return { hIndex, cIndex, nmIndex, totalCitations, totalSelfCitations, totalPublications };
}

module.exports = { calculateHIndex, calculateCIndex, calculateNmIndex, calculateAll };
