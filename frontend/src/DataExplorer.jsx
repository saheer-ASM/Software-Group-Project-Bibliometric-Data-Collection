import React, { useState, useCallback } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import './DataExplorer.css';

const DataExplorer = ({
  authorName,
  onBack,
  onNavigateToSettings,
  onNavigateToAbout,
  onNavigateToProfile,
  onLogout,
  hasSearchedAuthor,
  onResetSearch,
  onNavigateToExplorer
}) => {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [searchQuery, setSearchQuery] = useState(authorName || '');
  const [selectedField, setSelectedField] = useState('');
  const [selectedYear, setSelectedYear] = useState('');
  const [selectedHIndex, setSelectedHIndex] = useState('');
  const [selectedNmIndex, setSelectedNmIndex] = useState('');

  // Default "empty" profile shown before any data is fetched
  const defaultProfile = {
    author: 'Researcher',
    email: 'researcher@university.edu',
    totalPublications: 0,
    totalCitations: 0,
    totalSelfCitations: 0,
    nmIndex: 0,
    hIndex: 0,
    cScore: 0,
    trendData: [
      { name: 'P', publications: 200, citations: 240 },
      { name: 'Q', publications: 221, citations: 180 },
      { name: 'R', publications: 229, citations: 200 },
      { name: 'S', publications: 200, citations: 220 },
      { name: 'T', publications: 250, citations: 260 }
    ],
    publications: []
  };

  // Fetch author data from backend API
  const handleSearch = useCallback(async (queryOverride) => {
    const query = queryOverride || searchQuery;
    if (!query.trim()) {
      setError('Please enter an author name');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await fetch(`/api/search?author=${encodeURIComponent(query)}`);
      if (!response.ok) {
        throw new Error('Author not found');
      }
      const result = await response.json();
      setData(result);
    } catch (err) {
      // Simulated fallback data
      const simulatedData = {
        author: query,
        email: 'researcher@university.edu',
        totalPublications: 45,
        totalCitations: 320,
        totalSelfCitations: 28,
        nmIndex: 12,
        hIndex: 8,
        cScore: 2.85,
        trendData: [
          { name: 'P', publications: 200, citations: 240 },
          { name: 'Q', publications: 221, citations: 180 },
          { name: 'R', publications: 229, citations: 200 },
          { name: 'S', publications: 200, citations: 220 },
          { name: 'T', publications: 250, citations: 260 }
        ],
        publications: [
          {
            id: 1,
            title: 'Advanced Techniques in Machine Learning for Data Analysis',
            fields: ['Machine Learning', 'Data Science', 'AI', 'Analytics', 'Algorithms'],
            authors: ['Dr. Smith', 'Dr. Johnson', 'Dr. Williams'],
            selfCitations: 12,
            publishedYear: 2023,
            totalCitations: 45
          },
          {
            id: 2,
            title: 'Neural Network Applications in Healthcare Systems',
            fields: ['Neural Networks', 'Healthcare', 'Deep Learning', 'Medical AI', 'Systems'],
            authors: ['Dr. Brown', 'Dr. Davis', 'Dr. Miller'],
            selfCitations: 8,
            publishedYear: 2023,
            totalCitations: 62
          },
          {
            id: 3,
            title: 'Distributed Computing Frameworks for Big Data Processing',
            fields: ['Distributed Systems', 'Big Data', 'Cloud Computing', 'Frameworks', 'Scalability'],
            authors: ['Dr. Wilson', 'Dr. Taylor', 'Dr. Anderson'],
            selfCitations: 5,
            publishedYear: 2022,
            totalCitations: 38
          }
        ]
      };
      setData(simulatedData);
    } finally {
      setLoading(false);
    }
  }, [searchQuery]);

  // Auto-fetch when authorName prop changes
  React.useEffect(() => {
    if (authorName) {
      setSearchQuery(authorName);
      setTimeout(() => handleSearch(authorName), 100);
    }
  }, [authorName]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleResetSearchClick = () => {
    setData(null);
    setError('');
    setSearchQuery('');
    setSelectedField('');
    setSelectedYear('');
    setSelectedHIndex('');
    setSelectedNmIndex('');
    if (onResetSearch) onResetSearch();
  };

  const handleExportCSV = () => {
    const exportData = data || defaultProfile;
    const csvContent = [
      ['Author', exportData.author],
      ['Email', exportData.email],
      ['Total Publications', exportData.totalPublications],
      ['Total Citations', exportData.totalCitations],
      ['H-Index', exportData.hIndex],
      [],
      ['Title', 'Fields', 'Authors', 'Self Citations', 'Published Year', 'Total Citations']
    ];

    exportData.publications.forEach(pub => {
      csvContent.push([
        pub.title,
        pub.fields.join('; '),
        pub.authors.join('; '),
        pub.selfCitations,
        pub.publishedYear,
        pub.totalCitations
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
  const displayData = data || defaultProfile;

  return (
    <div className="de-container">
      {/* Header */}
      <header className="de-header">
        <div className="de-header-left">
          <i className='bx bxs-graduation'></i>
          <span className="de-logo">ScholarMetrics</span>
        </div>
        <div className="de-header-right">
          <nav className="de-nav">
            <a href="#dashboard" onClick={onBack} className="de-nav-link">Dashboard</a>
            <a href="#explorer" className="de-nav-link de-nav-active">Data Explorer</a>
            <a href="#about" onClick={onNavigateToAbout} className="de-nav-link">About Us</a>
            <button className="de-nav-link de-logout-btn" onClick={onLogout}>Logout</button>
          </nav>
          <div className="de-user-icon" onClick={onNavigateToProfile}>
            <i className='bx bxs-user-circle'></i>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="de-main">
        {/* Page title + Reset Search */}
        <div className="de-title-row">
          <h1 className="de-page-title">Data Explorer</h1>
          <button className="de-reset-btn" onClick={handleResetSearchClick}>
            <i className='bx bx-reset'></i> Reset Search
          </button>
        </div>

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
                <p className="de-author-email">{displayData.email}</p>
              </div>
            </div>

            <div className="de-metrics-grid">
              <div className="de-metric-box">
                <span className="de-metric-label">TOTAL PUBLICATIONS</span>
                <span className="de-metric-value">{displayData.totalPublications}</span>
              </div>
              <div className="de-metric-box">
                <span className="de-metric-label">TOTAL CITATIONS</span>
                <span className="de-metric-value">{displayData.totalCitations}</span>
              </div>
              <div className="de-metric-box">
                <span className="de-metric-label">TOTAL SELF CITATIONS</span>
                <span className="de-metric-value">{displayData.totalSelfCitations}</span>
              </div>
              <div className="de-metric-box">
                <span className="de-metric-label">NM INDEX</span>
                <span className="de-metric-value">{displayData.nmIndex}</span>
              </div>
              <div className="de-metric-box">
                <span className="de-metric-label">H INDEX</span>
                <span className="de-metric-value">{displayData.hIndex}</span>
              </div>
              <div className="de-metric-box">
                <span className="de-metric-label">C SCORE</span>
                <span className="de-metric-value">{displayData.cScore}</span>
              </div>
            </div>
          </div>

          {/* Right: Line Chart */}
          <div className="de-chart-area">
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={displayData.trendData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Line
                  type="monotone"
                  dataKey="publications"
                  stroke="#2a5298"
                  strokeWidth={2.5}
                  dot={{ r: 5, fill: '#2a5298' }}
                  activeDot={{ r: 7 }}
                />
                <Line
                  type="monotone"
                  dataKey="citations"
                  stroke="#e53e3e"
                  strokeWidth={2.5}
                  dot={{ r: 5, fill: '#e53e3e' }}
                  activeDot={{ r: 7 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>

        {error && <div className="de-error">{error}</div>}
        {loading && <div className="de-loading">Searching...</div>}

        {/* Filter Section */}
        <section className="de-filter-section">
          <div className="de-filter-header">
            <i className='bx bx-filter-alt'></i>
            <span>Filter</span>
          </div>
          <div className="de-filter-controls">
            <div className="de-filter-group">
              <label>Field</label>
              <select value={selectedField} onChange={(e) => setSelectedField(e.target.value)}>
                <option value="">Select Field</option>
                <option value="cs">Computer Science</option>
                <option value="bio">Biology</option>
                <option value="phys">Physics</option>
                <option value="math">Mathematics</option>
                <option value="med">Medicine</option>
              </select>
            </div>
            <div className="de-filter-group">
              <label>Year</label>
              <select value={selectedYear} onChange={(e) => setSelectedYear(e.target.value)}>
                <option value="">Select Year</option>
                <option value="2024">2024</option>
                <option value="2023">2023</option>
                <option value="2022">2022</option>
                <option value="2021">2021</option>
                <option value="2020">2020</option>
              </select>
            </div>
            <div className="de-filter-group">
              <label>H-Index</label>
              <select value={selectedHIndex} onChange={(e) => setSelectedHIndex(e.target.value)}>
                <option value="">Nm-Index</option>
                <option value="high">High (&gt;10)</option>
                <option value="medium">Medium (5-10)</option>
                <option value="low">Low (&lt;5)</option>
              </select>
            </div>
            <div className="de-filter-group">
              <label>Nm-Index</label>
              <select value={selectedNmIndex} onChange={(e) => setSelectedNmIndex(e.target.value)}>
                <option value="">Nm-Index</option>
                <option value="high">High (&gt;15)</option>
                <option value="medium">Medium (8-15)</option>
                <option value="low">Low (&lt;8)</option>
              </select>
            </div>
          </div>
        </section>

        {/* Publications Section */}
        {data && data.publications && data.publications.length > 0 && (
          <section className="de-publications">
            {data.publications.map((pub) => (
              <div key={pub.id} className="de-pub-card">
                <div className="de-pub-main">
                  <h3 className="de-pub-title">{pub.title}</h3>
                  <div className="de-pub-fields">
                    {pub.fields.map((field, idx) => (
                      <span key={idx} className="de-field-tag">{field}</span>
                    ))}
                  </div>
                  <div className="de-pub-authors">
                    <h4>Authors Contribution</h4>
                    <ul>
                      {pub.authors.map((author, idx) => (
                        <li key={idx}>{author}</li>
                      ))}
                    </ul>
                  </div>
                </div>
                <div className="de-pub-stats">
                  <div className="de-pub-stat">
                    <span className="de-pub-stat-label">Total Self Citations</span>
                    <span className="de-pub-stat-value">{pub.selfCitations}</span>
                  </div>
                  <div className="de-pub-stat">
                    <span className="de-pub-stat-label">Published Year</span>
                    <span className="de-pub-stat-value">{pub.publishedYear}</span>
                  </div>
                  <div className="de-pub-stat">
                    <span className="de-pub-stat-label">Total Citations</span>
                    <span className="de-pub-stat-value">{pub.totalCitations}</span>
                  </div>
                </div>
              </div>
            ))}
          </section>
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
