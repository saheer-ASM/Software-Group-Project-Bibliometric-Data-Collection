import React from 'react';
import '../DataExplorer.css';

// Weights arrive either as a proportion (0.66) or a percentage (66).
export const formatPercentage = (value, digits = 2) => {
  const number = Number(value || 0);
  const percentage = Math.abs(number) <= 1 ? number * 100 : number;
  return `${percentage.toFixed(digits)}%`;
};

/**
 * One publication's details: the card the Data Explorer lists for an author,
 * and the same card My Library shows for a saved paper, so a publication
 * looks and behaves identically wherever it is opened.
 *
 * The author-specific figures (self and adjusted citations, average ISC, "Your
 * contribution") belong to the author whose list the record was loaded for.
 */
export default function PublicationCard({
  publication: pub,
  label,
  saved = false,
  onToggleSave,
  expanded = false,
  onToggleExpanded,
  onSelectAuthor,
}) {
  const authors = pub.authors || [];
  const fieldDetails = pub.fieldDetails || [];
  return (
    <div className={`de-pub-card${expanded ? ' de-pub-card-expanded' : ''}`}>
      <div className="de-pub-main">
        <div className="de-pub-meta">
          <span className="de-publication-number">{label}</span>
          <span><i className='bx bx-calendar'></i>{pub.publishedYear || 'Year unavailable'}</span>
          {pub.source && <span><i className='bx bx-book-open'></i>{pub.source}</span>}
          <span><i className='bx bx-group'></i>{authors.length} authors</span>
          <span><i className='bx bx-sort-alt-2'></i>{pub.authorOrdering}</span>
          <button
            type="button"
            className={`de-paper-save${saved ? ' saved' : ''}`}
            onClick={() => onToggleSave(pub)}
          >
            <i className={saved ? 'bx bxs-bookmark' : 'bx bx-bookmark'}></i>
            {saved ? 'Saved' : 'Save paper'}
          </button>
        </div>
        <h3 className="de-pub-title">{pub.title}</h3>
        {pub.abstract && (
          <details className="de-pub-abstract">
            <summary>Read abstract</summary>
            <p>{pub.abstract}</p>
          </details>
        )}
        {/* Mobile only -- hidden by a media query on desktop, where
            every section below is already shown in full. */}
        <button
          type="button"
          className="de-pub-details-toggle"
          aria-expanded={expanded}
          aria-controls={`de-pub-stats-${pub.id} de-pub-secondary-${pub.id}`}
          onClick={() => onToggleExpanded(pub.id)}
        >
          <i
            className={expanded ? 'bx bx-chevron-up' : 'bx bx-chevron-down'}
            aria-hidden="true"
          />
          {expanded ? 'Hide Details' : 'Show Details'}
        </button>
      </div>
      <div className="de-pub-secondary" id={`de-pub-secondary-${pub.id}`}>
        <div className="de-pub-fields">
          <h4 className="de-fields-heading">Research fields</h4>
          <div className="de-field-tags">
          {fieldDetails.map((field, idx) => (
            <span key={idx} className="de-field-tag">
              {field.name} <strong>{formatPercentage(field.weight, 1)}</strong>
            </span>
          ))}
          </div>
        </div>
        <div className="de-pub-authors">
          <div className="de-authors-heading">
            <h4>Author contributions</h4>
            {!authors.some((author) => Number(author.weight) > 0) && (
              <span className="de-pending-badge">Not calculated</span>
            )}
          </div>
          <ul>
            {authors.map((author) => (
              <li key={author.id}>
                <button type="button" className="de-author-link" onClick={() => onSelectAuthor(author)}>
                  <span className="de-author-position">{author.position}</span>
                  <span className="de-author-name-text">{author.name}</span>
                  <strong>{Number(author.weight) > 0 ? formatPercentage(author.weight) : '—'}</strong>
                  <i className='bx bx-chevron-right' aria-hidden="true"></i>
                </button>
              </li>
            ))}
          </ul>
        </div>
      </div>
      <div className="de-pub-stats" id={`de-pub-stats-${pub.id}`}>
        <div className="de-pub-stat">
          <i className='bx bx-revision'></i>
          <span className="de-pub-stat-label">Self citations</span>
          <span className="de-pub-stat-value">{pub.selfCitations}</span>
        </div>
        <div className="de-pub-stat">
          <i className='bx bx-calendar'></i>
          <span className="de-pub-stat-label">Published</span>
          <span className="de-pub-stat-value">{pub.publishedYear || '—'}</span>
        </div>
        <div className="de-pub-stat">
          <i className='bx bx-quote-left'></i>
          <span className="de-pub-stat-label">Normal citations</span>
          <span className="de-pub-stat-value">{pub.totalCitations}</span>
        </div>
        <div className="de-pub-stat">
          <i className='bx bx-line-chart'></i>
          <span className="de-pub-stat-label">Adjusted citations</span>
          <span className="de-pub-stat-value">{Number(pub.adjustedCitations).toFixed(3)}</span>
        </div>
        <div className="de-pub-stat">
          <i className='bx bx-analyse'></i>
          <span className="de-pub-stat-label">Average ISC</span>
          <span className="de-pub-stat-value">{Number(pub.averageIsc).toFixed(3)}</span>
        </div>
        <div className="de-pub-stat">
          <i className='bx bx-pie-chart-alt-2'></i>
          <span className="de-pub-stat-label">Your contribution</span>
          <span className={`de-pub-stat-value ${Number(pub.authorContributionWeight) > 0 ? '' : 'de-value-pending'}`}>
            {Number(pub.authorContributionWeight) > 0 ? formatPercentage(pub.authorContributionWeight) : 'Not calculated'}
          </span>
        </div>
      </div>
    </div>
  );
}
