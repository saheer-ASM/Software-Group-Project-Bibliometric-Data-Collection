import React, { useEffect, useState } from 'react';
import { API_BASE_URL } from '../../config/api';
import AuthorSelector from './AuthorSelector';
import ComparisonChart from './ComparisonChart';
import MetricComparison from './MetricComparison';
import './ComparisonDashboard.css';

export default function ComparisonDashboard({ initialAuthor }) {
  const [selectedAuthors, setSelectedAuthors] = useState(initialAuthor?.id ? [initialAuthor] : []);
  const [comparison, setComparison] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (initialAuthor?.id) setSelectedAuthors((current) => current.some((author) => author.id === initialAuthor.id) ? current : [initialAuthor, ...current].slice(0, 3));
  }, [initialAuthor]);

  const compareAuthors = async () => {
    if (selectedAuthors.length < 2) return;
    setLoading(true);
    setError('');
    try {
      const ids = selectedAuthors.map((author) => author.id).join(',');
      const response = await fetch(`${API_BASE_URL}/api/compare?authorIds=${encodeURIComponent(ids)}`);
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.message || 'Unable to compare authors.');
      setComparison(payload);
    } catch (requestError) {
      setError(requestError.message || 'Unable to compare authors.');
    } finally {
      setLoading(false);
    }
  };

  const updateSelection = (authors) => {
    setSelectedAuthors(authors);
    setComparison(null);
    setError('');
  };

  return <div className="ac-inline">
      <AuthorSelector selectedAuthors={selectedAuthors} onChange={updateSelection} onCompare={compareAuthors} loading={loading} />
      {error && <div className="ac-error" role="alert"><i className="bx bx-error-circle"></i>{error}</div>}
      {comparison?.authors?.length > 0 && <>
        <MetricComparison authors={comparison.authors} />
        <ComparisonChart authors={comparison.authors} />
      </>}
      {!comparison && !loading && <div className="ac-empty"><i className="bx bx-git-compare"></i><h2>Select researchers to begin</h2><p>Add at least two authors, then choose “Compare authors”.</p></div>}
  </div>;
}
