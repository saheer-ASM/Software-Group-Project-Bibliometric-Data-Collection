import React from 'react';

const metrics = [
  ['NM Index', 'nmIndex', 3],
  ['Total Cites Score', 'cScore', 3],
  ['Publications', 'publications', 0],
  ['Total Citations', 'citations', 0],
  ['Adjusted Citations', 'adjustedCitations', 3],
  ['Self Citations', 'selfCitations', 0],
];

export default function MetricComparison({ authors }) {
  return <section className="ac-metric-section" aria-labelledby="metric-comparison-title">
    <div className="ac-section-heading"><div><h2 id="metric-comparison-title">Metric comparison</h2><p>Database-calculated performance values for each researcher.</p></div></div>
    <div className="ac-metric-grid">
      {metrics.map(([label, key, digits]) => <article className="ac-metric-card" key={key}>
        <h3>{label}</h3>
        {authors.map((author, index) => <div className="ac-metric-row" key={author.authorId}>
          <span><i className={`ac-author-dot ac-color-${index}`}></i>{author.name}</span>
          <strong>{Number(author[key] || 0).toFixed(digits)}</strong>
        </div>)}
      </article>)}
    </div>
  </section>;
}
