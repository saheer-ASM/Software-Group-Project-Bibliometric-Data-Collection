
import React, { useEffect, useState, useRef } from 'react';
import { API_BASE_URL } from './config/api';
import './Dashboard.css';
import AppNavbar from './AppNavbar';

const EMPTY_STATS = { publications: null, authors: null, fields: null };

function getCachedStats() {
  try {
    const cached = JSON.parse(localStorage.getItem('dashboardStats'));
    return cached && ['publications', 'authors', 'fields'].every((key) => Number.isFinite(Number(cached[key])))
      ? cached
      : EMPTY_STATS;
  } catch (_error) {
    return EMPTY_STATS;
  }
}

const AnimatedCounter = ({ value, loading }) => {
  const target = Number(value ?? 0);
  const [displayed, setDisplayed] = useState(0);
  const currentValue = useRef(0);

  useEffect(() => {
    const start = currentValue.current;
    const difference = target - start;
    if (!difference || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      currentValue.current = target;
      setDisplayed(target);
      return undefined;
    }

    const startedAt = performance.now();
    let frameId;
    const animate = (time) => {
      const progress = Math.min((time - startedAt) / 1400, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      const next = Math.round(start + difference * eased);
      currentValue.current = next;
      setDisplayed(next);
      if (progress < 1) frameId = requestAnimationFrame(animate);
    };
    frameId = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frameId);
  }, [target]);

  return <span className={loading ? 'stat-number-loading' : ''}>{displayed.toLocaleString()}</span>;
};

const Dashboard = ({ username = "User", onLogout, onNavigateToExplorer, onNavigateToSettings, onNavigateToAbout, onNavigateToProfile, onNavigateToLibrary, hasSearchedAuthor, onResetSearch }) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [authorSuggestions, setAuthorSuggestions] = useState([]);
  const [suggestionsOpen, setSuggestionsOpen] = useState(false);
  const [suggestionsLoading, setSuggestionsLoading] = useState(false);
  const [activeSuggestion, setActiveSuggestion] = useState(-1);
  const [stats, setStats] = useState(getCachedStats);
  const [statsLoading, setStatsLoading] = useState(true);
  const [statsError, setStatsError] = useState('');
  const scrollContainerRef = useRef(null);

  useEffect(() => {
    const controller = new AbortController();

    async function loadStats() {
      try {
        const response = await fetch(`${API_BASE_URL}/api/stats`, { signal: controller.signal });
        if (!response.ok) throw new Error('Stats request failed');
        const freshStats = await response.json();
        setStats(freshStats);
        localStorage.setItem('dashboardStats', JSON.stringify(freshStats));
        setStatsError('');
      } catch (error) {
        if (error.name !== 'AbortError') setStatsError('Live statistics are temporarily unavailable');
      } finally {
        setStatsLoading(false);
      }
    }

    loadStats();
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const query = searchQuery.trim();
    if (!suggestionsOpen || query.length < 2) {
      setAuthorSuggestions([]);
      setSuggestionsLoading(false);
      setActiveSuggestion(-1);
      return undefined;
    }

    const controller = new AbortController();
    const timer = setTimeout(async () => {
      setSuggestionsLoading(true);
      try {
        const response = await fetch(`${API_BASE_URL}/api/authors?q=${encodeURIComponent(query)}`, {
          signal: controller.signal
        });
        if (!response.ok) throw new Error('Author lookup failed');
        setAuthorSuggestions(await response.json());
        setActiveSuggestion(-1);
      } catch (error) {
        if (error.name !== 'AbortError') setAuthorSuggestions([]);
      } finally {
        if (!controller.signal.aborted) setSuggestionsLoading(false);
      }
    }, 250);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [searchQuery, suggestionsOpen]);

  const handleScroll = (direction) => {
    if (scrollContainerRef.current) {
      const scrollAmount = 300;
      const targetScroll = scrollContainerRef.current.scrollLeft + (direction === 'left' ? -scrollAmount : scrollAmount);
      scrollContainerRef.current.scrollTo({
        left: targetScroll,
        behavior: 'smooth'
      });
    }
  };

  const popularFields = [
    { name: 'Medicine', image: 'https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?w=400&h=300&fit=crop' },
    { name: 'Psychology', image: 'https://images.unsplash.com/photo-1559757148-5c350d0d3c56?w=400&h=300&fit=crop' },
    { name: 'Engineering', image: 'https://images.unsplash.com/photo-1581094794329-c8112a89af12?w=400&h=300&fit=crop' },
    { name: 'Economics', image: 'https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=400&h=300&fit=crop' },
    { name: 'Computer Science', image: 'https://images.unsplash.com/photo-1517694712202-14dd9538aa97?w=400&h=300&fit=crop' },
    { name: 'Biology', image: 'https://images.unsplash.com/photo-1532187863486-abf9dbad1b69?w=400&h=300&fit=crop' },
    { name: 'Chemistry', image: 'https://images.unsplash.com/photo-1603126857599-f6e157fa2fe6?w=400&h=300&fit=crop' },
    { name: 'Physics', image: 'https://images.unsplash.com/photo-1636466497217-26a8cbeaf0aa?w=400&h=300&fit=crop' },
    { name: 'Mathematics', image: 'https://images.unsplash.com/photo-1635070041078-e363dbe005cb?w=400&h=300&fit=crop' },
    { name: 'Environmental Science', image: 'https://images.unsplash.com/photo-1542601906990-b4d3fb778b09?w=400&h=300&fit=crop' },
    { name: 'Sociology', image: 'https://images.unsplash.com/photo-1529156069898-49953e39b3ac?w=400&h=300&fit=crop' },
    { name: 'History', image: 'https://images.unsplash.com/photo-1461360370896-922624d12aa1?w=400&h=300&fit=crop' },
    { name: 'Political Science', image: 'https://images.unsplash.com/photo-1529107386315-e1a2ed48a620?w=400&h=300&fit=crop' },
    { name: 'Law', image: 'https://images.unsplash.com/photo-1589829545856-d10d557cf95f?w=400&h=300&fit=crop' },
    { name: 'Education', image: 'https://images.unsplash.com/photo-1503676260728-1c00da094a0b?w=400&h=300&fit=crop' }
  ];

  const handleSearch = (e) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      if (activeSuggestion >= 0 && authorSuggestions[activeSuggestion]) {
        selectAuthor(authorSuggestions[activeSuggestion]);
        return;
      }
      setSuggestionsOpen(false);
      // Navigate to Data Explorer with author name
      onNavigateToExplorer(searchQuery.trim());
    }
  };

  const selectAuthor = (author) => {
    setSearchQuery(author.name);
    setSuggestionsOpen(false);
    setAuthorSuggestions([]);
    setActiveSuggestion(-1);
    onNavigateToExplorer(author.name);
  };

  const handleSearchKeyDown = (event) => {
    if (!suggestionsOpen || !authorSuggestions.length) {
      if (event.key === 'Escape') setSuggestionsOpen(false);
      return;
    }
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setActiveSuggestion((current) => (current + 1) % authorSuggestions.length);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setActiveSuggestion((current) => current <= 0 ? authorSuggestions.length - 1 : current - 1);
    } else if (event.key === 'Escape') {
      setSuggestionsOpen(false);
    }
  };

  const handleFieldClick = (fieldName) => {
    console.log('Field clicked:', fieldName);
    // Add navigation logic here
  };

  return (
    <div className="dashboard-container">
      <AppNavbar activePage="dashboard" onDashboard={() => {}} onExplorer={onNavigateToExplorer} onLibrary={onNavigateToLibrary} onAbout={onNavigateToAbout} onProfile={onNavigateToProfile} onLogout={onLogout} />

      {/* Main Content */}
      <main className="dashboard-main">
        {/* Welcome Section */}
        <div className="welcome-section">
          <h2>Welcome {username}!</h2>
        </div>

        {/* Quick Stats */}
        <section className="stats-section">
          <h2 className="section-title">Quick Stats</h2>
          <div className="stats-grid">
            <div className="stat-card">
              <div className="stat-number"><AnimatedCounter value={stats.publications} loading={statsLoading} /></div>
              <div className="stat-label">Publications</div>
            </div>
            <div className="stat-card highlight">
              <div className="stat-number"><AnimatedCounter value={stats.authors} loading={statsLoading} /></div>
              <div className="stat-label">Authors</div>
            </div>
            <div className="stat-card">
              <div className="stat-number"><AnimatedCounter value={stats.fields} loading={statsLoading} /></div>
              <div className="stat-label">Fields</div>
            </div>
          </div>
          {statsError && <p role="status" className="stats-error">{statsError}</p>}
        </section>

        {/* Author Search */}
        <section className="search-section">
          <h2 className="section-title">Author Search</h2>
          <form onSubmit={handleSearch} className="search-form">
            <input
              type="text"
              placeholder="Enter Author's Name"
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setSuggestionsOpen(true);
              }}
              onFocus={() => setSuggestionsOpen(true)}
              onKeyDown={handleSearchKeyDown}
              className="search-input"
              role="combobox"
              aria-autocomplete="list"
              aria-expanded={suggestionsOpen && searchQuery.trim().length >= 2}
              aria-controls="dashboard-author-suggestions"
              aria-activedescendant={activeSuggestion >= 0 ? `dashboard-author-${activeSuggestion}` : undefined}
            />
            <button type="submit" className="search-btn">
              <i className='bx bx-search'></i>
            </button>
            {suggestionsOpen && searchQuery.trim().length >= 2 && (
              <div id="dashboard-author-suggestions" className="dashboard-author-suggestions" role="listbox">
                {suggestionsLoading ? (
                  <div className="dashboard-suggestion-message">Searching authors…</div>
                ) : authorSuggestions.length ? authorSuggestions.map((author, index) => (
                  <button
                    id={`dashboard-author-${index}`}
                    key={author.id}
                    type="button"
                    role="option"
                    aria-selected={index === activeSuggestion}
                    className={`dashboard-author-option${index === activeSuggestion ? ' active' : ''}`}
                    onMouseDown={(event) => event.preventDefault()}
                    onMouseEnter={() => setActiveSuggestion(index)}
                    onClick={() => selectAuthor(author)}
                  >
                    <span className="dashboard-author-avatar"><i className="bx bxs-user" /></span>
                    <span className="dashboard-author-details">
                      <strong>{author.name}</strong>
                      <small>{author.id}</small>
                    </span>
                    <i className="bx bx-right-arrow-alt" />
                  </button>
                )) : (
                  <div className="dashboard-suggestion-message">No matching authors found</div>
                )}
              </div>
            )}
            <a href="#library" className="nav-link" onClick={onNavigateToLibrary}>My Library</a>
          </form>
        </section>

        {/* Popular Fields */}
        <section className="fields-section">
          <h2 className="section-title">Popular Fields</h2>
          <div className="fields-wrapper">
            <button 
              className="scroll-btn scroll-btn-left" 
              onClick={() => handleScroll('left')}
              aria-label="Scroll left"
            >
              <i className='bx bx-chevron-left'></i>
            </button>
            <div className="fields-scroll-container" ref={scrollContainerRef}>
              <div className="fields-grid">
                {popularFields.map((field, index) => (
                  <div
                    key={index}
                    className="field-card"
                    onClick={() => handleFieldClick(field.name)}
                  >
                    <img src={field.image} alt={field.name} className="field-image" />
                    <div className="field-overlay">
                      <h3 className="field-name">{field.name}</h3>
                    </div>
                  </div>
                ))}
              </div>
            </div>
            <button 
              className="scroll-btn scroll-btn-right" 
              onClick={() => handleScroll('right')}
              aria-label="Scroll right"
            >
              <i className='bx bx-chevron-right'></i>
            </button>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="dashboard-footer">
        <div className="footer-content">
          <div className="footer-section">
            <div className="footer-title">
              <i className='bx bx-file'></i>
              <h3>ScholarMetrics</h3>
            </div>
            <p>Revolutionizing research evaluation through intelligent automation and comprehensive data collection across global scholarly databases.</p>
          </div>

          <div className="footer-section">
            <h4>Quick Links</h4>
            <ul>
              <li><a href="#dashboard">Dashboard</a></li>
              <li><a href="#explorer">Data Explorer</a></li>
              <li><a href="#settings">Settings</a></li>
              <li><a href="#about">About Us</a></li>
            </ul>
          </div>

          <div className="footer-section">
            <h4>Resources</h4>
            <ul>
              <li><a href="#docs">Documentation</a></li>
              <li><a href="#api">API Reference</a></li>
              <li><a href="#tutorials">Tutorials</a></li>
              <li><a href="#faq">FAQ</a></li>
            </ul>
          </div>

          <div className="footer-section">
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

export default Dashboard;
