const count = (value) => Math.max(0, Number(value) || 0);

export function publicationYears(publications) {
  return [...new Set(publications.map(p => Number(p.publishedYear))
    .filter(year => Number.isInteger(year) && year > 0))].sort((a, b) => a - b);
}

export function citationValue(publication, view = 'normal') {
  return count(view === 'adjusted' ? publication.adjustedCitations : publication.totalCitations);
}

export function impactLevel(value) {
  return value >= 10 ? 'high' : value >= 5 ? 'medium' : value > 0 ? 'low' : 'uncited';
}

// UI classification only: preserve the API values and all research calculations.
export function filterPublications(publications, filters, authorId) {
  return publications.filter(p => {
    const { query = '', field = '', years, contribution = '', citationType = '', impact = '', view = 'normal' } = filters;
    if (query.trim() && !p.title?.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase())) return false;
    if (field && !p.fields?.includes(field)) return false;
    if (years && (!p.publishedYear || Number(p.publishedYear) < years[0] || Number(p.publishedYear) > years[1])) return false;
    const normal = citationValue(p);
    const author = p.authors?.find(a => a.id === authorId);
    const weight = count(p.authorContributionWeight);
    const percentage = weight <= 1 ? weight * 100 : weight;
    if (contribution && !({
      primary: Number(author?.position) === 1,
      major: percentage >= 25,
      minor: percentage > 0 && percentage < 25,
      coauthor: Number(author?.position) > 1,
    })[contribution]) return false;
    if (citationType === 'external' && normal - count(p.selfCitations) <= 0) return false;
    if (citationType === 'self' && count(p.selfCitations) <= 0) return false;
    if (citationType === 'adjusted' && citationValue(p, 'adjusted') <= 0) return false;
    const level = impactLevel(citationValue(p, view));
    if (impact && level !== impact) return false;
    return true;
  });
}
