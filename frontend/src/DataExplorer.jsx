import React, { useEffect, useMemo, useState, useCallback } from 'react';
import './DataExplorer.css';

const API = process.env.REACT_APP_API_URL || 'http://localhost:5000';

function getToken() {
  return localStorage.getItem('token');
}

const DataExplorer = ({
  authorName = '',
  onBack,
  onNavigateToAbout,
  onNavigateToProfile,
  onNavigateToSettings,
  onLogout,
  hasSearchedAuthor,
  onResetSearch,
  onNavigateToExplorer,
}) => {
  const [searchQuery,   setSearchQuery]   = useState(authorName);
  const [searchResults, setSearchResults] = useState([]);
  const [selectedAuthor, setSelectedAuthor] = useState(null);
  const [publications,  setPublications]  = useState([]);
  const [loading,       setLoading]       = useState(false);
  const [error,         setError]         = useState('');
  const [filterField,   setFilterField]   = useState('');
  const [filterYear,    setFilterYear]    = useState('');

  // Search authors by name
  const doSearch = useCallback(async (name) => {
    if (!name || name.trim().length < 2) return;
    setLoading(true);
    setError('');
    try {
      const res = await fetch(
        `${API}/api/authors/search?name=${encodeURIComponent(name.trim())}`,
        { headers: { Authorization: `Bearer ${getToken()}` } }
      );
      if (!res.ok) throw new Error((await res.json()).message || 'Search failed');
      const { authors } = await res.json();
      setSearchResults(authors);
      if (authors.length === 1) {
        loadAuthorDetails(authors[0].author_id);
      } else if (authors.length === 0) {
        setError('No authors found for that name.');
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  // Load full author profile + publications
  const loadAuthorDetails = useCallback(async (authorId, field = '', year = '') => {
    setLoading(true);
    setError('');
    try {
      const params = new URLSearchParams();
      if (field) params.set('field', field);
      if (year)  params.set('year',  year);
      const qs = params.toString() ? `?${params}` : '';

      const res = await fetch(
        `${API}/api/authors/${authorId}${qs}`,
        { headers: { Authorization: `Bearer ${getToken()}` } }
      );
      if (!res.ok) throw new Error((await res.json()).message || 'Failed to load author');
      const { author, publications: pubs } = await res.json();
      setSelectedAuthor(author);
      setPublications(pubs);
      setSearchResults([]);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  // Trigger search when authorName prop changes (from Dashboard)
  useEffect(() => {
    if (authorName) {
      setSearchQuery(authorName);
      doSearch(authorName);
    }
  }, [authorName, doSearch]);

  // Re-fetch when filters change
  useEffect(() => {
    if (selectedAuthor) {
      loadAuthorDetails(selectedAuthor.author_id, filterField, filterYear);
    }
  }, [filterField, filterYear]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSearch = (e) => {
    e.preventDefault();
    const next = searchQuery.trim();
    if (next) {
      setSelectedAuthor(null);
      setPublications([]);
      doSearch(next);
      onNavigateToExplorer(next);
    }
  };

  const handleClear = () => {
    setSearchQuery('');
    setSelectedAuthor(null);
    setPublications([]);
    setSearchResults([]);
    setError('');
    onResetSearch();
  };

  const handleExportCSV = () => {
    if (!selectedAuthor || publications.length === 0) return;

    const headers = ['Title', 'Year', 'Venue', 'Total Citations', 'Self Citations', 'Fields'];
    const rows = publications.map((p) => [
      `"${p.title.replace(/"/g, '""')}"`,
      p.year || '',
      `"${(p.venue || '').replace(/"/g, '""')}"`,
      p.total_citations,
      p.self_citations,
      `"${(Array.isArray(p.fields) ? p.fields.join('; ') : '')}"`,
    ]);

    const csv = [headers, ...rows].map((r) => r.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href     = url;
    a.download = `${selectedAuthor.name.replace(/\s+/g, '_')}_publications.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const heroMetrics = useMemo(() => {
    if (!selectedAuthor) {
      return [
        { label: 'Total Publications',  value: '--' },
        { label: 'Total Citations',      value: '--' },
        { label: 'Total Self Citations', value: '--' },
        { label: 'H-Index',             value: '--' },
        { label: 'C Score',             value: '--' },
        { label: 'Nm-Index',            value: '--' },
      ];
    }
    return [
      { label: 'Total Publications',  value: selectedAuthor.totalPublications  ?? '--' },
      { label: 'Total Citations',     value: selectedAuthor.totalCitations      ?? '--' },
      { label: 'Total Self Citations',value: selectedAuthor.totalSelfCitations  ?? '--' },
      { label: 'H-Index',            value: selectedAuthor.hIndex               ?? '--' },
      { label: 'C Score',            value: selectedAuthor.cIndex               ?? '--' },
      { label: 'Nm-Index',           value: selectedAuthor.nmIndex              ?? '--' },
    ];
  }, [selectedAuthor]);

  const displayName  = selectedAuthor?.name  || authorName || 'Search an Author';
  const displayEmail = selectedAuthor?.email || (selectedAuthor?.name
    ? `${selectedAuthor.name.replace(/\s+/g, '.').toLowerCase()}@university.edu`
    : '');

  return (
    <div className="data-explorer-page">
      <header className="explorer-header">
        <div className="brand-block">
          <div className="brand-icon">A</div>
          <div>
            <div className="brand-name">Acade Mine</div>
            <div className="brand-subtitle">Data Explorer</div>
          </div>
        </div>

        <nav className="explorer-nav">
          <button type="button" onClick={onBack}>Dashboard</button>
          <button type="button" onClick={onNavigateToProfile}>Settings</button>
          <button type="button" onClick={onNavigateToAbout}>About Us</button>
          <button type="button" className="logout-button" onClick={onLogout}>Logout</button>
        </nav>
      </header>

      <main className="explorer-main">
        <section className="hero-section">
          <div className="hero-card">
            <div className="hero-card-left">
              <span className="eyebrow">Data Explorer</span>
              <h1>Discover scholarly publication trends</h1>
              <p>Review author metrics, publication performance, and contribution highlights in one unified space.</p>

              <form onSubmit={handleSearch} className="explorer-search-form">
                <input
                  type="text"
                  placeholder="Search author by name…"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
                <button type="submit" disabled={loading}>
                  {loading ? '…' : 'Search'}
                </button>
                {searchQuery && (
                  <button type="button" onClick={handleClear}>Clear</button>
                )}
              </form>

              {error && <p className="explorer-error">{error}</p>}

              {searchResults.length > 1 && (
                <ul className="search-results-list">
                  {searchResults.map((a) => (
                    <li key={a.author_id}>
                      <button
                        type="button"
                        onClick={() => loadAuthorDetails(a.author_id)}
                      >
                        <strong>{a.name}</strong>
                        {a.affiliation && <span> — {a.affiliation}</span>}
                      </button>
                    </li>
                  ))}
                </ul>
              )}

              <div className="hero-metrics">
                {heroMetrics.slice(0, 3).map((m) => (
                  <div key={m.label} className="hero-metric-card">
                    <span>{m.label}</span>
                    <strong>{m.value}</strong>
                  </div>
                ))}
              </div>
            </div>

            <div className="hero-card-right">
              <div className="profile-banner">
                <div className="profile-avatar">{displayName.charAt(0).toUpperCase()}</div>
                <div>
                  <div className="profile-name">{displayName}</div>
                  {selectedAuthor?.affiliation && (
                    <div className="profile-affiliation">{selectedAuthor.affiliation}</div>
                  )}
                  <div className="profile-email">{displayEmail}</div>
                </div>
              </div>

              <div className="metrics-grid">
                {heroMetrics.slice(3).map((m) => (
                  <div key={m.label} className="metric-badge">
                    <span>{m.label}</span>
                    <strong>{m.value}</strong>
                  </div>
                ))}
              </div>

              <div className="chart-card">
                <div className="chart-header">
                  <div>
                    <span className="eyebrow">Performance</span>
                    <h2>Publications vs Citations</h2>
                  </div>
                </div>
                <div className="line-chart">
                  <div className="line-grid" />
                  <div className="line-path" />
                  <div className="points">
                    <span style={{ left: '10%' }} />
                    <span style={{ left: '30%' }} />
                    <span style={{ left: '50%' }} />
                    <span style={{ left: '70%' }} />
                    <span style={{ left: '90%' }} />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="filter-section">
          <div className="filter-row">
            <div className="filter-field">
              <label>Field</label>
              <select value={filterField} onChange={(e) => setFilterField(e.target.value)}>
                <option value="">All Fields</option>
                <option>Computer Science</option>
                <option>Biology</option>
                <option>Engineering</option>
                <option>Medicine</option>
                <option>Physics</option>
                <option>Mathematics</option>
              </select>
            </div>
            <div className="filter-field">
              <label>Year</label>
              <select value={filterYear} onChange={(e) => setFilterYear(e.target.value)}>
                <option value="">All Years</option>
                {[2024, 2023, 2022, 2021, 2020, 2019, 2018].map((y) => (
                  <option key={y}>{y}</option>
                ))}
              </select>
            </div>
            <div className="filter-field">
              <label>H-Index</label>
              <select disabled>
                <option>{selectedAuthor?.hIndex ?? '--'}</option>
              </select>
            </div>
            <div className="filter-field">
              <label>Nm-Index</label>
              <select disabled>
                <option>{selectedAuthor?.nmIndex ?? '--'}</option>
              </select>
            </div>
          </div>
        </section>

        <section className="publication-section">
          {loading && <p className="explorer-loading">Loading…</p>}

          {!loading && publications.length === 0 && selectedAuthor && (
            <p className="explorer-empty">No publications found for the selected filters.</p>
          )}

          {publications.map((pub) => (
            <article key={pub.publication_id} className="publication-card">
              <div className="publication-main">
                <div>
                  <h3>{pub.title}</h3>
                  {pub.venue && <p className="pub-venue">{pub.venue} · {pub.year}</p>}
                  <div className="field-bars">
                    {(Array.isArray(pub.fields) ? pub.fields : []).map((f) => (
                      <span key={f}>{f}</span>
                    ))}
                  </div>
                </div>
                <div className="publication-details">
                  <span>Co-Authors</span>
                  {(pub.coAuthors || []).length > 0
                    ? pub.coAuthors.map((a) => <p key={a.author_id}>{a.name}</p>)
                    : <p>—</p>}
                </div>
              </div>

              <div className="publication-stats">
                <div>
                  <span>Self Citations</span>
                  <strong>{pub.self_citations}</strong>
                </div>
                <div>
                  <span>Published Year</span>
                  <strong>{pub.year || '—'}</strong>
                </div>
                <div>
                  <span>Total Citations</span>
                  <strong>{pub.total_citations}</strong>
                </div>
              </div>
            </article>
          ))}

          <div className="explorer-actions">
            <button
              className="primary-button"
              type="button"
              onClick={handleExportCSV}
              disabled={!selectedAuthor || publications.length === 0}
            >
              Export CSV
            </button>
          </div>
        </section>
      </main>

      <footer className="explorer-footer">
        <div className="footer-left">
          <h3>Acade Mine</h3>
          <p>Revolutionizing research evaluation through intelligent automation and comprehensive data collection across global scholarly databases.</p>
        </div>
        <div className="footer-links">
          <div>
            <h4>Quick Links</h4>
            <ul>
              <li><button type="button" onClick={onBack}>Dashboard</button></li>
              <li><button type="button">Data Explorer</button></li>
              <li><button type="button" onClick={onNavigateToSettings}>Settings</button></li>
              <li><button type="button" onClick={onNavigateToAbout}>About Us</button></li>
            </ul>
          </div>
          <div>
            <h4>Contact</h4>
            <ul>
              <li><button type="button">Support Center</button></li>
              <li><a href="mailto:info@academine.edu">info@academine.edu</a></li>
              <li><button type="button">Send Feedback</button></li>
              <li><button type="button">Report an Issue</button></li>
            </ul>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default DataExplorer;
