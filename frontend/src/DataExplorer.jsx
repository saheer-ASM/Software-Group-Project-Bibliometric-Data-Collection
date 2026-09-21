import React, { useState, useCallback, useMemo, useRef } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { API_BASE_URL } from './config/api';
import { downloadAuthorPdf, getLibrary, recordRecentAuthor, savePaperToCollection, toggleSavedAuthor, toggleSavedPaper } from './services/researchLibrary';
import './DataExplorer.css';
import AppNavbar from './AppNavbar';
import ComparisonDashboard from './components/comparison/ComparisonDashboard';

const MetricCard = ({ title, value, tooltip }) => {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef(null);
  const tooltipId = React.useId();

  React.useEffect(() => {
    if (!isOpen) return undefined;

    const closeOnOutsideClick = (event) => {
      if (!containerRef.current?.contains(event.target)) setIsOpen(false);
    };
    const closeOnEscape = (event) => {
      if (event.key === 'Escape') setIsOpen(false);
    };

    document.addEventListener('pointerdown', closeOnOutsideClick);
    document.addEventListener('keydown', closeOnEscape);
    return () => {
      document.removeEventListener('pointerdown', closeOnOutsideClick);
      document.removeEventListener('keydown', closeOnEscape);
    };
  }, [isOpen]);

  return (
    <div className="de-metric-box">
      <span className="de-metric-label">{title}</span>
      <span className="de-metric-value">{value}</span>
      <span className={`de-metric-help${isOpen ? ' is-open' : ''}`} ref={containerRef}>
        <button
          type="button"
          className="de-metric-info"
          aria-label={`About ${title}`}
          aria-expanded={isOpen}
          aria-controls={tooltipId}
          onClick={() => setIsOpen((open) => !open)}
        >
          <span aria-hidden="true">ⓘ</span>
        </button>
        <span
          id={tooltipId}
          className="de-metric-tooltip"
          role="tooltip"
          aria-hidden={!isOpen}
        >
          {tooltip}
        </span>
      </span>
    </div>
  );
};

const DataExplorer = ({
  authorName,
  onBack,
  onNavigateToSettings,
  onNavigateToAbout,
  onNavigateToProfile,
  onLogout,
  hasSearchedAuthor,
  onResetSearch,
  onNavigateToExplorer,
  onNavigateToLibrary,
  user
}) => {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [searchQuery, setSearchQuery] = useState(authorName || '');
  const [selectedField, setSelectedField] = useState('');
  const [selectedYear, setSelectedYear] = useState('');
  const [selectedHIndex, setSelectedHIndex] = useState('');
  const [selectedNmIndex, setSelectedNmIndex] = useState('');
  const [paperQuery, setPaperQuery] = useState('');
  const [paperSuggestionsOpen, setPaperSuggestionsOpen] = useState(false);
  const [activePaperSuggestion, setActivePaperSuggestion] = useState(-1);
  const [authorHistory, setAuthorHistory] = useState([]);
  const [authorSuggestions, setAuthorSuggestions] = useState([]);
  const [suggestionsOpen, setSuggestionsOpen] = useState(false);
  const [suggestionsLoading, setSuggestionsLoading] = useState(false);
  const [activeSuggestion, setActiveSuggestion] = useState(-1);
  const searchControllerRef = useRef(null);
  const userId = user?.id || user?.email;
  const [library, setLibrary] = useState(() => getLibrary(userId));
  const [paperToSave, setPaperToSave] = useState(null);
  const [selectedCollectionId, setSelectedCollectionId] = useState('');
  const [newCollectionName, setNewCollectionName] = useState('');
  const [comparisonOpen, setComparisonOpen] = useState(false);

  React.useEffect(() => {
    const syncLibrary = (event) => setLibrary(event.detail || getLibrary(userId));
    window.addEventListener('research-library-changed', syncLibrary);
    return () => window.removeEventListener('research-library-changed', syncLibrary);
  }, [userId]);

  React.useEffect(() => {
    if (data?.authorId) recordRecentAuthor(userId, { id: data.authorId, name: data.author });
  }, [data?.authorId, data?.author, userId]);

  const formatPercentage = (value, digits = 2) => {
    const number = Number(value || 0);
    const percentage = Math.abs(number) <= 1 ? number * 100 : number;
    return `${percentage.toFixed(digits)}%`;
  };

  // Default "empty" profile shown before any data is fetched
  const defaultProfile = {
    author: 'Researcher',
    authorId: '',
    totalPublications: 0,
    totalCitations: 0,
    totalSelfCitations: 0,
    nmIndex: 0,
    hIndex: 0,
    cScore: 0,
    totalAdjustedCitations: 0,
    careerCompensation: 0,
    trendData: [],
    publications: []
  };

  // Fetch author data from backend API
  const handleSearch = useCallback(async (queryOverride, authorIdOverride = '') => {
    const query = queryOverride || searchQuery;
    if (!query.trim() && !authorIdOverride) {
      setError('Please enter an author name');
      return;
    }

    searchControllerRef.current?.abort();
    const controller = new AbortController();
    setSuggestionsLoading(true);
    searchControllerRef.current = controller;

    setLoading(true);
    setError('');
    setSelectedField('');
    setSelectedYear('');
    setSelectedHIndex('');
    setSelectedNmIndex('');
    setPaperQuery('');
    setPaperSuggestionsOpen(false);

    try {
      const params = new URLSearchParams();
      if (query.trim()) params.set('author', query.trim());
      if (authorIdOverride) params.set('authorId', authorIdOverride);
      const response = await fetch(`${API_BASE_URL}/api/search?${params.toString()}`, {
        signal: controller.signal,
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.message || 'Author not found');
      }
      const result = await response.json();
      setData(result);
      return result;
    } catch (err) {
      if (err.name !== 'AbortError') {
        setError(err.message || 'Search failed');
      }
      return null;
    } finally {
      if (searchControllerRef.current === controller) setLoading(false);
    }
  }, [searchQuery]);

  const handleAuthorSelect = async (author) => {
    if (!author?.id || loading) return;
    if (data?.authorId === author.id) return;
    const currentAuthor = data?.authorId ? { id: data.authorId, name: data.author } : null;
    const currentQuery = searchQuery;
    setSearchQuery(author.name);
    window.scrollTo({ top: 0, behavior: 'smooth' });
    const result = await handleSearch(author.name, author.id);
    if (result && currentAuthor) {
      setAuthorHistory((history) => [...history, currentAuthor]);
    } else if (!result) {
      setSearchQuery(currentQuery);
    }
  };

  const handlePreviousAuthor = async () => {
    if (!authorHistory.length || loading) return;
    const previousAuthor = authorHistory[authorHistory.length - 1];
    const currentQuery = searchQuery;
    setSearchQuery(previousAuthor.name);
    window.scrollTo({ top: 0, behavior: 'smooth' });
    const result = await handleSearch(previousAuthor.name, previousAuthor.id);
    if (result) {
      setAuthorHistory((history) => history.slice(0, -1));
    } else {
      setSearchQuery(currentQuery);
    }
  };

  React.useEffect(() => {
    const query = searchQuery.trim();
    if (!suggestionsOpen || query.length < 2) {
      setAuthorSuggestions([]);
      setActiveSuggestion(-1);
      setSuggestionsLoading(false);
      return undefined;
    }

    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/authors?q=${encodeURIComponent(query)}`, {
          signal: controller.signal,
        });
        if (!response.ok) throw new Error('Suggestions unavailable');
        setAuthorSuggestions(await response.json());
        setActiveSuggestion(-1);
      } catch (suggestionError) {
        if (suggestionError.name !== 'AbortError') setAuthorSuggestions([]);
      } finally {
        if (!controller.signal.aborted) setSuggestionsLoading(false);
      }
    }, 250);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [searchQuery, suggestionsOpen]);

  const selectSuggestedAuthor = async (author) => {
    setSuggestionsOpen(false);
    setAuthorSuggestions([]);
    setSearchQuery(author.name);
    setAuthorHistory([]);
    await handleSearch(author.name, author.id);
  };

  const handleExplorerSearchSubmit = async (event) => {
    event.preventDefault();
    if (activeSuggestion >= 0 && authorSuggestions[activeSuggestion]) {
      await selectSuggestedAuthor(authorSuggestions[activeSuggestion]);
      return;
    }
    setSuggestionsOpen(false);
    setAuthorHistory([]);
    await handleSearch(searchQuery);
  };

  const handleSearchKeyDown = (event) => {
    if (!suggestionsOpen || !authorSuggestions.length) return;
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setActiveSuggestion((index) => Math.min(index + 1, authorSuggestions.length - 1));
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setActiveSuggestion((index) => Math.max(index - 1, 0));
    } else if (event.key === 'Escape') {
      setSuggestionsOpen(false);
    }
  };

  // Auto-fetch when authorName prop changes
  React.useEffect(() => {
    if (authorName) {
      setSearchQuery(authorName);
      const timer = setTimeout(() => handleSearch(authorName), 100);
      return () => clearTimeout(timer);
    }
    return undefined;
  }, [authorName]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleResetSearchClick = () => {
    setData(null);
    setError('');
    setSearchQuery('');
    setSelectedField('');
    setSelectedYear('');
    setSelectedHIndex('');
    setSelectedNmIndex('');
    setPaperQuery('');
    setPaperSuggestionsOpen(false);
    setAuthorHistory([]);
    if (onResetSearch) onResetSearch();
  };

  const handleExportCSV = () => {
    const exportData = data || defaultProfile;
    const csvContent = [
      ['Author', exportData.author],
      ['Author ID', exportData.authorId],
      ['Total Publications', exportData.totalPublications],
      ['Total Citations', exportData.totalCitations],
      ['H-Index', exportData.hIndex],
      ['Adjusted Citations', exportData.totalAdjustedCitations],
      ['Total Cites Score', exportData.cScore],
      [],
      ['Title', 'Fields', 'Authors', 'Contribution Weight', 'Self Citations', 'ISC', 'Year', 'Citations', 'Adjusted Citations']
    ];

    const publicationsToExport = data ? filteredPublications : exportData.publications;
    publicationsToExport.forEach(pub => {
      csvContent.push([
        pub.title,
        pub.fields.join('; '),
        pub.authors.map(author => `${author.name} (${author.weight})`).join('; '),
        pub.authorContributionWeight,
        pub.selfCitations,
        pub.averageIsc,
        pub.publishedYear,
        pub.totalCitations,
        pub.adjustedCitations
      ]);
    });

    const csvString = csvContent.map(row => row.map(cell => `"${cell}"`).join(',')).join('\n');
    const element = document.createElement('a');
    element.setAttribute('href', 'data:text/csv;charset=utf-8,' + encodeURIComponent(csvString));
    element.setAttribute('download', `${exportData.author}_data.csv`);
    element.style.display = 'none';
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
  };

  // The displayed profile is either fetched data or the default placeholder
  const displayData = data || {
    ...defaultProfile,
    author: loading && searchQuery ? searchQuery : defaultProfile.author,
  };
  const profileSubtitle = loading
    ? 'Retrieving researcher profile and publication metrics…'
    : data?.authorId
      ? `Research profile · ${data.authorId}`
      : 'Enter an author name to explore their research profile';
  const availableFields = useMemo(() => [...new Set(
    (data?.publications || []).flatMap((publication) => publication.fields || [])
  )].sort((a, b) => a.localeCompare(b)), [data]);
  const availableYears = useMemo(() => [...new Set(
    (data?.publications || []).map((publication) => publication.publishedYear).filter(Boolean)
  )].sort((a, b) => b - a), [data]);
  const paperSuggestions = useMemo(() => {
    const query = paperQuery.trim().toLocaleLowerCase();
    if (query.length < 2) return [];
    return (data?.publications || [])
      .filter((publication) => publication.title?.toLocaleLowerCase().includes(query))
      .slice(0, 8);
  }, [data, paperQuery]);
  const filteredPublications = useMemo(() => (data?.publications || []).filter((publication) => {
    const paperMatches = !paperQuery.trim()
      || publication.title?.toLocaleLowerCase().includes(paperQuery.trim().toLocaleLowerCase());
    const fieldMatches = !selectedField || publication.fields?.includes(selectedField);
    const yearMatches = !selectedYear || String(publication.publishedYear) === selectedYear;
    const citationMatches = !selectedHIndex
      || (selectedHIndex === 'uncited' && publication.totalCitations === 0)
      || (selectedHIndex === 'cited' && publication.totalCitations > 0)
      || (selectedHIndex === 'high' && publication.totalCitations >= 10);
    const contributionAvailable = publication.authors?.some((author) => Number(author.weight) > 0);
    const contributionMatches = !selectedNmIndex
      || (selectedNmIndex === 'calculated' && contributionAvailable)
      || (selectedNmIndex === 'pending' && !contributionAvailable)
      || (selectedNmIndex === 'major' && Number(publication.authorContributionWeight) >= 25);
    return paperMatches && fieldMatches && yearMatches && citationMatches && contributionMatches;
  }), [data, paperQuery, selectedField, selectedYear, selectedHIndex, selectedNmIndex]);

  const selectPaperSuggestion = (publication) => {
    setPaperQuery(publication.title);
    setPaperSuggestionsOpen(false);
    setActivePaperSuggestion(-1);
  };

  const handlePaperSearchKeyDown = (event) => {
    if (event.key === 'Escape') {
      setPaperSuggestionsOpen(false);
      return;
    }
    if (!paperSuggestions.length) return;
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setActivePaperSuggestion((index) => Math.min(index + 1, paperSuggestions.length - 1));
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setActivePaperSuggestion((index) => Math.max(index - 1, 0));
    } else if (event.key === 'Enter' && activePaperSuggestion >= 0) {
      event.preventDefault();
      selectPaperSuggestion(paperSuggestions[activePaperSuggestion]);
    }
  };

  const requestPaperSave = (publication) => {
    const paper = { id: publication.id, title: publication.title, publishedYear: publication.publishedYear, authorId: data.authorId, authorName: data.author };
    if (library.savedPapers.some((item) => item.id === publication.id)) {
      toggleSavedPaper(userId, paper);
      return;
    }
    setPaperToSave(paper);
    setSelectedCollectionId(library.collections[0]?.id || '');
    setNewCollectionName('');
  };

  const confirmPaperSave = (event) => {
    event.preventDefault();
    if (!paperToSave || (!selectedCollectionId && !newCollectionName.trim())) return;
    savePaperToCollection(userId, paperToSave, selectedCollectionId, newCollectionName);
    setPaperToSave(null);
  };

  const clearFilters = () => {
    setPaperQuery('');
    setPaperSuggestionsOpen(false);
    setActivePaperSuggestion(-1);
    setSelectedField('');
    setSelectedYear('');
    setSelectedHIndex('');
    setSelectedNmIndex('');
  };

  const activeFilterCount = [paperQuery.trim(), selectedField, selectedYear, selectedHIndex, selectedNmIndex]
    .filter(Boolean).length;

  return (
    <div className="de-container">
      <AppNavbar activePage="explorer" onDashboard={onBack} onExplorer={() => {}} onLibrary={onNavigateToLibrary} onAbout={onNavigateToAbout} onProfile={onNavigateToProfile} onLogout={onLogout} />

      {/* Main Content */}
      <main className="de-main">
        {/* Page title + Reset Search */}
        <div className="de-title-row">
          <h1 className="de-page-title">Data Explorer</h1>
          <div className="de-title-actions">
            {authorHistory.length > 0 && (
              <button className="de-previous-author-btn" onClick={handlePreviousAuthor} disabled={loading}>
                <i className='bx bx-arrow-back'></i> Previous researcher
              </button>
            )}
            {data && (
              <button className="de-reset-btn" onClick={() => downloadAuthorPdf({ ...data, publications: filteredPublications })}>
                <i className='bx bx-download'></i> Download summary
              </button>
            )}
            {data && (
              <button
                className={`de-reset-btn${library.savedAuthors.some((author) => author.id === data.authorId) ? ' de-saved-btn' : ''}`}
                onClick={() => toggleSavedAuthor(userId, { id: data.authorId, name: data.author })}
              >
                <i className={library.savedAuthors.some((author) => author.id === data.authorId) ? 'bx bxs-bookmark' : 'bx bx-bookmark'}></i>
                {library.savedAuthors.some((author) => author.id === data.authorId) ? 'Author saved' : 'Save author'}
              </button>
            )}
            <button className="de-reset-btn" onClick={handleResetSearchClick}>
              <i className='bx bx-reset'></i> Reset Search
            </button>
          </div>
        </div>

        <form className="de-author-search" onSubmit={handleExplorerSearchSubmit}>
          <label htmlFor="explorer-author-search">Search another researcher</label>
          <div className="de-author-search-box">
            <i className='bx bx-search' aria-hidden="true"></i>
            <input
              id="explorer-author-search"
              type="search"
              value={searchQuery}
              placeholder="Start typing an author’s name…"
              autoComplete="off"
              role="combobox"
              aria-autocomplete="list"
              aria-expanded={suggestionsOpen && authorSuggestions.length > 0}
              aria-controls="author-suggestions"
              aria-activedescendant={activeSuggestion >= 0 ? `author-suggestion-${activeSuggestion}` : undefined}
              onChange={(event) => {
                setSearchQuery(event.target.value);
                setSuggestionsOpen(true);
              }}
              onFocus={() => setSuggestionsOpen(true)}
              onBlur={() => setTimeout(() => setSuggestionsOpen(false), 120)}
              onKeyDown={handleSearchKeyDown}
            />
            <button type="submit" disabled={loading || !searchQuery.trim()}>
              {loading ? 'Loading…' : 'View profile'}
            </button>
            {suggestionsOpen && searchQuery.trim().length >= 2 && (
              <div id="author-suggestions" className="de-author-suggestions" role="listbox">
                {suggestionsLoading ? (
                  <div className="de-suggestion-empty">Searching authors…</div>
                ) : authorSuggestions.length > 0 ? authorSuggestions.map((author, index) => (
                  <button
                    id={`author-suggestion-${index}`}
                    key={author.id}
                    type="button"
                    role="option"
                    aria-selected={index === activeSuggestion}
                    className={index === activeSuggestion ? 'active' : ''}
                    onMouseDown={(event) => event.preventDefault()}
                    onClick={() => selectSuggestedAuthor(author)}
                  >
                    <span className="de-suggestion-avatar"><i className='bx bxs-user'></i></span>
                    <span><strong>{author.name}</strong><small>{author.id}</small></span>
                    <i className='bx bx-chevron-right'></i>
                  </button>
                )) : (
                  <div className="de-suggestion-empty">No matching authors found</div>
                )}
              </div>
            )}
          </div>
        </form>

        {error && (
          <div className="de-error" role="alert" aria-live="assertive">
            <i className='bx bx-error-circle'></i>
            <span>{error}</span>
          </div>
        )}

        {/* Author Profile Card — always visible */}
        <section className="de-profile-card">
          {/* Left: Avatar + name + metrics */}
          <div className="de-profile-left">
            <div className="de-profile-top">
              <div className="de-avatar">
                <i className='bx bxs-user-circle'></i>
              </div>
              <div className="de-profile-info">
                <h2 className="de-author-name">{displayData.author}</h2>
                <p className="de-author-email">{profileSubtitle}</p>
              </div>
            </div>

            <div className="de-metrics-grid">
              <MetricCard
                title="TOTAL PUBLICATIONS"
                value={displayData.totalPublications}
                tooltip="Total number of research papers published by this author."
              />
              <MetricCard
                title="TOTAL CITATIONS"
                value={displayData.totalCitations}
                tooltip="Total number of citations received by this author's publications."
              />
              <MetricCard
                title="TOTAL SELF CITATIONS"
                value={displayData.totalSelfCitations}
                tooltip="Number of citations where the author cites their own previous publications."
              />
              <MetricCard
                title="NM INDEX"
                value={displayData.nmIndex}
                tooltip="Overall research impact score calculated by combining multiple research performance indicators."
              />
              <MetricCard
                title="H INDEX"
                value={displayData.hIndex}
                tooltip="Largest number h such that the author has at least h publications with at least h citations each."
              />
              <MetricCard
                title="C SCORE"
                value={Number(displayData.cScore).toFixed(3)}
                tooltip="Adjusted research impact score based on citations, author contribution, field, and publication factors."
              />
              <MetricCard
                title="ADJUSTED CITATIONS"
                value={Number(displayData.totalAdjustedCitations).toFixed(3)}
                tooltip="Citation count after reducing the influence of self-citations for a fairer impact measurement."
              />
              <MetricCard
                title="CAREER COMPENSATION"
                value={Number(displayData.careerCompensation).toFixed(3)}
                tooltip="Factor used to account for research career length when calculating the author's impact score."
              />
            </div>
          </div>

          {/* Right: Line Chart */}
          <div className="de-chart-area">
            <div className="de-chart-heading">
              <div>
                <h3>Research activity over time</h3>
                <p>Publications released and citations received in each year</p>
              </div>
              <span>{displayData.trendData.length} years</span>
            </div>
            <div className="de-chart-plot">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={displayData.trendData} margin={{ top: 20, right: 20, left: 0, bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="publications"
                  name="Publications"
                  stroke="#2a5298"
                  strokeWidth={2.5}
                  dot={{ r: 5, fill: '#2a5298' }}
                  activeDot={{ r: 7 }}
                />
                <Line
                  type="monotone"
                  dataKey="adjustedCitations"
                  name="Adjusted citations received"
                  stroke="#16a085"
                  strokeWidth={2.5}
                  dot={{ r: 4, fill: '#16a085' }}
                />
                <Line
                  type="monotone"
                  dataKey="citations"
                  name="Citations received"
                  stroke="#e53e3e"
                  strokeWidth={2.5}
                  dot={{ r: 5, fill: '#e53e3e' }}
                  activeDot={{ r: 7 }}
                />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </section>

        {loading && (
          <div className="de-loading" role="status" aria-live="polite">
            <div>
              <strong>Preparing research profile</strong>
              <span>We’re gathering publication and citation metrics. This may take a moment.</span>
            </div>
          </div>
        )}

        {data && (
          <section className={`de-comparison-entry${comparisonOpen ? ' is-expanded' : ''}`} aria-labelledby="de-comparison-title">
            <div className="de-comparison-entry-summary">
              <span className="de-comparison-entry-icon"><i className="bx bx-git-compare"></i></span>
              <div>
                <h2 id="de-comparison-title">Author Comparison</h2>
                <p>Compare this researcher’s publications, citations, Total Cites Score, and NM Index with other authors.</p>
              </div>
              <button type="button" aria-expanded={comparisonOpen} onClick={() => setComparisonOpen((open) => !open)}>
                {comparisonOpen ? 'Close comparison' : 'Compare researchers'}
                <i className={`bx ${comparisonOpen ? 'bx-chevron-up' : 'bx-chevron-down'}`}></i>
              </button>
            </div>
            {comparisonOpen && (
              <ComparisonDashboard
                key={data.authorId}
                initialAuthor={{ id: data.authorId, name: data.author }}
              />
            )}
          </section>
        )}

        <section className="de-publication-portfolio">
          <div className="de-portfolio-heading">
            <div className="de-portfolio-title">
              <span className="de-portfolio-icon"><i className='bx bx-library'></i></span>
              <div>
                <h2>Publication Portfolio</h2>
                <p>Browse, filter, and review this researcher’s publication record and impact metrics.</p>
              </div>
            </div>
            <span className="de-portfolio-count">{data?.publications?.length || 0} publications</span>
          </div>

        {/* Filter Section */}
        <section className="de-filter-section">
          <div className="de-filter-header">
            <div className="de-filter-heading">
              <i className='bx bx-filter-alt'></i>
              <div>
                <span>Filter publications</span>
                <small>Narrow results using publication-level information</small>
              </div>
            </div>
            <div className="de-filter-actions">
              {activeFilterCount > 0 && <span>{activeFilterCount} active</span>}
              <button type="button" className="de-clear-filters" onClick={clearFilters}>Clear filters</button>
            </div>
          </div>
          <div className="de-filter-controls">
            <div className="de-filter-group de-paper-search-group">
              <label htmlFor="publication-search">Publication title</label>
              <div className="de-paper-search-box">
                <i className="bx bx-search" aria-hidden="true"></i>
                <input
                  id="publication-search"
                  type="search"
                  value={paperQuery}
                  placeholder="Search paper titles"
                  autoComplete="off"
                  role="combobox"
                  aria-autocomplete="list"
                  aria-expanded={paperSuggestionsOpen && paperQuery.trim().length >= 2}
                  aria-controls="paper-suggestions"
                  aria-activedescendant={activePaperSuggestion >= 0 ? `paper-suggestion-${activePaperSuggestion}` : undefined}
                  onChange={(event) => {
                    setPaperQuery(event.target.value);
                    setPaperSuggestionsOpen(true);
                    setActivePaperSuggestion(-1);
                  }}
                  onFocus={() => setPaperSuggestionsOpen(true)}
                  onBlur={() => setTimeout(() => setPaperSuggestionsOpen(false), 120)}
                  onKeyDown={handlePaperSearchKeyDown}
                />
                {paperQuery && (
                  <button type="button" aria-label="Clear publication search" onClick={() => setPaperQuery('')}>
                    <i className="bx bx-x"></i>
                  </button>
                )}
                {paperSuggestionsOpen && paperQuery.trim().length >= 2 && (
                  <div id="paper-suggestions" className="de-paper-suggestions" role="listbox">
                    {paperSuggestions.length ? paperSuggestions.map((publication, index) => (
                      <button
                        id={`paper-suggestion-${index}`}
                        key={publication.id}
                        type="button"
                        role="option"
                        aria-selected={index === activePaperSuggestion}
                        className={index === activePaperSuggestion ? 'active' : ''}
                        onMouseDown={(event) => event.preventDefault()}
                        onMouseEnter={() => setActivePaperSuggestion(index)}
                        onClick={() => selectPaperSuggestion(publication)}
                      >
                        <i className="bx bx-file"></i>
                        <span><strong>{publication.title}</strong><small>{publication.publishedYear || 'Year unavailable'}</small></span>
                      </button>
                    )) : <div className="de-paper-suggestion-empty">No matching publications found</div>}
                  </div>
                )}
              </div>
            </div>
            <div className="de-filter-group">
              <label>Field</label>
              <select value={selectedField} onChange={(e) => setSelectedField(e.target.value)}>
                <option value="">All fields</option>
                {availableFields.map((field) => <option key={field} value={field}>{field}</option>)}
              </select>
            </div>
            <div className="de-filter-group">
              <label>Year</label>
              <select value={selectedYear} onChange={(e) => setSelectedYear(e.target.value)}>
                <option value="">All years</option>
                {availableYears.map((year) => <option key={year} value={String(year)}>{year}</option>)}
              </select>
            </div>
            <div className="de-filter-group">
              <label>Citation status</label>
              <select value={selectedHIndex} onChange={(e) => setSelectedHIndex(e.target.value)}>
                <option value="">All citation levels</option>
                <option value="cited">Cited publications</option>
                <option value="uncited">Not yet cited</option>
                <option value="high">10+ citations</option>
              </select>
            </div>
            <div className="de-filter-group">
              <label>Contribution</label>
              <select value={selectedNmIndex} onChange={(e) => setSelectedNmIndex(e.target.value)}>
                <option value="">All contribution states</option>
                <option value="calculated">Calculated</option>
                <option value="pending">Not calculated</option>
                <option value="major">Author contribution 25%+</option>
              </select>
            </div>
          </div>
          <div className="de-filter-summary" aria-live="polite">
            <i className='bx bx-list-ul'></i>
            <span>Showing <strong>{filteredPublications.length}</strong> of <strong>{data?.publications?.length || 0}</strong> publications</span>
          </div>
        </section>

        {/* Publications Section */}
        {data && filteredPublications.length > 0 && (
          <section className="de-publications">
            {filteredPublications.map((pub, publicationIndex) => (
              <div key={pub.id} className="de-pub-card">
                <div className="de-pub-main">
                  <div className="de-pub-meta">
                    <span className="de-publication-number">Paper {String(publicationIndex + 1).padStart(2, '0')}</span>
                    <span><i className='bx bx-calendar'></i>{pub.publishedYear || 'Year unavailable'}</span>
                    {pub.source && <span><i className='bx bx-book-open'></i>{pub.source}</span>}
                    <span><i className='bx bx-group'></i>{pub.authors.length} authors</span>
                    <span><i className='bx bx-sort-alt-2'></i>{pub.authorOrdering}</span>
                    <button
                      type="button"
                      className={`de-paper-save${library.savedPapers.some((paper) => paper.id === pub.id) ? ' saved' : ''}`}
                      onClick={() => requestPaperSave(pub)}
                    >
                      <i className={library.savedPapers.some((paper) => paper.id === pub.id) ? 'bx bxs-bookmark' : 'bx bx-bookmark'}></i>
                      {library.savedPapers.some((paper) => paper.id === pub.id) ? 'Saved' : 'Save paper'}
                    </button>
                  </div>
                  <h3 className="de-pub-title">{pub.title}</h3>
                  {pub.abstract && (
                    <details className="de-pub-abstract">
                      <summary>Read abstract</summary>
                      <p>{pub.abstract}</p>
                    </details>
                  )}
                  <div className="de-pub-fields">
                    <h4 className="de-fields-heading">Research fields</h4>
                    <div className="de-field-tags">
                    {pub.fieldDetails.map((field, idx) => (
                      <span key={idx} className="de-field-tag">
                        {field.name} <strong>{formatPercentage(field.weight, 1)}</strong>
                      </span>
                    ))}
                    </div>
                  </div>
                  <div className="de-pub-authors">
                    <div className="de-authors-heading">
                      <h4>Author contributions</h4>
                      {!pub.authors.some((author) => Number(author.weight) > 0) && (
                        <span className="de-pending-badge">Not calculated</span>
                      )}
                    </div>
                    <ul>
                      {pub.authors.map((author) => (
                        <li key={author.id}>
                          <button type="button" className="de-author-link" onClick={() => handleAuthorSelect(author)}>
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
                <div className="de-pub-stats">
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
                    <span className="de-pub-stat-label">Citations</span>
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
            ))}
          </section>
        )}
        {data && data.publications?.length > 0 && filteredPublications.length === 0 && (
          <div className="de-no-results">
            <i className='bx bx-filter-alt'></i>
            <h3>No publications match these filters</h3>
            <p>Try a different field, year, citation level, or contribution status.</p>
            <button type="button" onClick={clearFilters}>Clear filters</button>
          </div>
        )}
        </section>

        {paperToSave && (
          <div className="de-collection-modal" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setPaperToSave(null); }}>
            <form className="de-collection-dialog" role="dialog" aria-modal="true" aria-labelledby="collection-dialog-title" onSubmit={confirmPaperSave}>
              <div className="de-collection-dialog-header">
                <span><i className="bx bx-folder-plus"></i></span>
                <div><small>SAVE PUBLICATION</small><h2 id="collection-dialog-title">Choose a collection</h2></div>
                <button type="button" aria-label="Close" onClick={() => setPaperToSave(null)}><i className="bx bx-x"></i></button>
              </div>
              <p className="de-collection-paper-title">{paperToSave.title}</p>
              {library.collections.length > 0 && <label>Existing collection<select value={newCollectionName ? '' : selectedCollectionId} onChange={(event) => { setSelectedCollectionId(event.target.value); setNewCollectionName(''); }}><option value="" disabled>Select a collection</option>{library.collections.map((collection) => <option key={collection.id} value={collection.id}>{collection.name} ({collection.paperIds.length})</option>)}</select></label>}
              <div className="de-collection-divider"><span>or create a new collection</span></div>
              <label>New collection name<input type="text" value={newCollectionName} onChange={(event) => { setNewCollectionName(event.target.value); if (event.target.value) setSelectedCollectionId(''); }} placeholder="e.g. Machine Learning" maxLength="60" autoFocus={!library.collections.length} /></label>
              <div className="de-collection-dialog-actions"><button type="button" onClick={() => setPaperToSave(null)}>Cancel</button><button type="submit" disabled={!selectedCollectionId && !newCollectionName.trim()}><i className="bx bxs-bookmark"></i> Save to collection</button></div>
            </form>
          </div>
        )}

        {/* Export CSV Button */}
        <div className="de-export-section">
          <button className="de-export-btn" onClick={handleExportCSV}>
            Click here to Export CSV
          </button>
        </div>
      </main>

      {/* Footer */}
      <footer className="de-footer">
        <div className="de-footer-content">
          <div className="de-footer-section">
            <div className="de-footer-brand">
              <i className='bx bx-file'></i>
              <h3>ScholarMetrics</h3>
            </div>
            <p>Revolutionizing research evaluation through intelligent automation and comprehensive data collection across global scholarly databases.</p>
          </div>
          <div className="de-footer-section">
            <h4>Quick Links</h4>
            <ul>
              <li><a href="#dashboard" onClick={onBack}>Dashboard</a></li>
              <li><a href="#explorer">Data Explorer</a></li>
              <li><a href="#settings" onClick={onNavigateToSettings}>Settings</a></li>
              <li><a href="#about" onClick={onNavigateToAbout}>About Us</a></li>
            </ul>
          </div>
          <div className="de-footer-section">
            <h4>Resources</h4>
            <ul>
              <li><a href="#docs">Documentation</a></li>
              <li><a href="#api">API Reference</a></li>
              <li><a href="#tutorials">Tutorials</a></li>
              <li><a href="#faq">FAQ</a></li>
            </ul>
          </div>
          <div className="de-footer-section">
            <h4>Contact</h4>
            <ul>
              <li><a href="#support">Support Center</a></li>
              <li><a href="mailto:info@academine.edu">info@academine.edu</a></li>
              <li><a href="#feedback">Send Feedback</a></li>
              <li><a href="#report">Report an Issue</a></li>
            </ul>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default DataExplorer;
