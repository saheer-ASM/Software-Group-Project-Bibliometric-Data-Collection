import React, { useMemo, useState } from 'react';
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

const colors = ['#134074', '#c43d4d', '#16a085'];
const metricOptions = {
  totalPublications: 'Total Publications',
  totalCitations: 'Total Citations',
  hIndex: 'H-index',
  selfCitations: 'Self Citations',
  adjustedCitations: 'Adjusted citations',
};

export default function ComparisonChart({ authors }) {
  const [trendMetric, setTrendMetric] = useState('totalCitations');
  const barData = ['nmIndex', 'cScore', 'citations', 'adjustedCitations'].map((metric) => ({
    metric: { nmIndex: 'NM Index', cScore: 'C Score', citations: 'Citations', adjustedCitations: 'Adjusted cites' }[metric],
    ...Object.fromEntries(authors.map((author) => [author.authorId, Number(author[metric] || 0)])),
  }));
  const trendData = useMemo(() => {
    const years = new Map();
    authors.forEach((author) => author.trendData.forEach((point) => {
      const row = years.get(point.year) || {
        year: point.year,
        ...Object.fromEntries(authors.map((item) => [item.authorId, 0])),
      };
      row[author.authorId] = Number(point[trendMetric] || 0);
      years.set(point.year, row);
    }));
    return [...years.values()].sort((a, b) => String(a.year).localeCompare(String(b.year)));
  }, [authors, trendMetric]);

  return <div className="ac-chart-grid">
    <section className="ac-panel ac-chart-card">
      <div className="ac-section-heading"><div><h2>Research impact</h2><p>Side-by-side comparison across key metrics.</p></div></div>
      <div className="ac-chart-area"><ResponsiveContainer width="100%" height="100%">
        <BarChart data={barData} margin={{ top: 10, right: 10, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" /><XAxis dataKey="metric" tick={{ fontSize: 11 }} /><YAxis tick={{ fontSize: 11 }} /><Tooltip /><Legend />
          {authors.map((author, index) => <Bar key={author.authorId} dataKey={author.authorId} name={author.name} fill={colors[index]} radius={[4, 4, 0, 0]} />)}
        </BarChart>
      </ResponsiveContainer></div>
    </section>
    <section className="ac-panel ac-chart-card">
      <div className="ac-section-heading ac-chart-heading"><div><h2>Citation growth comparison</h2><p>Annual activity based on citing-paper publication year.</p></div>
        <select value={trendMetric} onChange={(event) => setTrendMetric(event.target.value)} aria-label="Select comparison metric">
          {Object.entries(metricOptions).map(([value, label]) => <option value={value} key={value}>{label}</option>)}
        </select>
      </div>
      <div className="ac-chart-area"><ResponsiveContainer width="100%" height="100%">
        <LineChart data={trendData} margin={{ top: 10, right: 15, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" /><XAxis dataKey="year" tick={{ fontSize: 11 }} /><YAxis tick={{ fontSize: 11 }} /><Tooltip /><Legend />
          {authors.map((author, index) => <Line key={author.authorId} type="monotone" dataKey={author.authorId} name={author.name} stroke={colors[index]} strokeWidth={2.5} connectNulls />)}
        </LineChart>
      </ResponsiveContainer></div>
    </section>
  </div>;
}
