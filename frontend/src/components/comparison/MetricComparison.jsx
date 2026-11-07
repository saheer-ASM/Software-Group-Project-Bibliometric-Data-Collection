import React from 'react';
import { formatDecimal } from '../../services/formatNumber';

// [label, key, decimal]: decimal values use the app-wide format (at most 3
// decimals); counts are whole numbers.
const metrics = [
  ['NM Index', 'nmIndex', true],
  ['Total Cites Score', 'cScore', true],
  ['Publications', 'publications', false],
  ['Total Citations', 'citations', false],
  ['Adjusted Citations', 'adjustedCitations', true],
  ['Self Citations', 'selfCitations', false],
];

export default function MetricComparison({ authors }) {
  return <section className="ac-metric-section" aria-labelledby="metric-comparison-title">
    <div className="ac-section-heading"><div><h2 id="metric-comparison-title">Metric comparison</h2><p>Database-calculated performance values for each researcher.</p></div></div>
    <div className="ac-metric-grid">
      {metrics.map(([label, key, decimal]) => <article className="ac-metric-card" key={key}>
        <h3>{label}</h3>
        {authors.map((author, index) => <div className="ac-metric-row" key={author.authorId}>
          <span><i className={`ac-author-dot ac-color-${index}`}></i>{author.name}</span>
          <strong>{decimal ? formatDecimal(author[key] || 0) : Number(author[key] || 0).toFixed(0)}</strong>
        </div>)}
      </article>)}
    </div>
  </section>;
}
