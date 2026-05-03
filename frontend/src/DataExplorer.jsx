import React, { useState } from 'react';
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
  const [searchQuery, setSearchQuery] = useState(authorName);
  const [selectedField, setSelectedField] = useState('');
  const [selectedYear, setSelectedYear] = useState('');
  const [selectedHIndex, setSelectedHIndex] = useState('');
  const [selectedNmIndex, setSelectedNmIndex] = useState('');

  // Simulated author data - replace with actual API call
  const handleSearch = async (e) => {
    e?.preventDefault?.();
    if (!searchQuery.trim()) {
      setError('Please enter an author name');
      return;
    }

    setLoading(true);
    setError('');
    
    try {
      // TODO: Replace with actual API call to your backend
      // const response = await fetch(`/api/search?author=${searchQuery}`);
      // const result = await response.json();
      
      // Simulated data for now
      const simulatedData = {
        author: searchQuery,
        email: 'researcher@university.edu',
        totalPublications: 250,
        totalCitations: 250,
        totalSelfCitations: 250,
        nmIndex: 250,
        hIndex: 250,
        cScore: 250,
        publications: [
          {
            id: 1,
            title: 'Title of Publication',
            fields: ['Field 01', 'Field 02', 'Field 03', 'Field 04', 'Field 05'],
            authors: ['Mr. XXXX', 'Mr. YYYY', 'Mr. ZZZZ'],
            selfCitations: 250,
            publishedYear: 250,
            totalCitations: 250
          },
          {
            id: 2,
            title: 'Title of Publication',
            fields: ['Field 01', 'Field 02', 'Field 03', 'Field 04', 'Field 05'],
            authors: ['Mr. XXXX', 'Mr. YYYY', 'Mr. ZZZZ'],
            selfCitations: 250,
            publishedYear: 250,
            totalCitations: 250
          },
          {
            id: 3,
            title: 'Title of Publication',
            fields: ['Field 01', 'Field 02', 'Field 03', 'Field 04', 'Field 05'],
            authors: ['Mr. XXXX', 'Mr. YYYY', 'Mr. ZZZZ'],
            selfCitations: 250,
            publishedYear: 250,
            totalCitations: 250
          }
        ]
      };
      
      setData(simulatedData);
    } catch (err) {
      setError(err.message || 'Failed to fetch author data');
    } finally {
      setLoading(false);
    }
  };

  // Auto-fetch when authorName changes
  React.useEffect(() => {
    if (authorName) {
      setSearchQuery(authorName);
      // Trigger search
      setTimeout(() => handleSearch(), 100);
    }
  }, [authorName]);

  const handleExportCSV = () => {
    if (!data) return;
    
    // Create CSV content
    const csvContent = [
      ['Author', data.author],
      ['Email', data.email],
      ['Total Publications', data.totalPublications],
      ['Total Citations', data.totalCitations],
      ['H-Index', data.hIndex],
      [],
      ['Title', 'Fields', 'Authors', 'Self Citations', 'Published Year', 'Total Citations']
    ];

    data.publications.forEach(pub => {
      csvContent.push([
        pub.title,
        pub.fields.join('; '),
        pub.authors.join('; '),
        pub.selfCitations,
        pub.publishedYear,
        pub.totalCitations
      ]);
    });

    // Convert to CSV string
    const csvString = csvContent.map(row => row.map(cell => `"${cell}"`).join(',')).join('\n');
    
    // Download
    const element = document.createElement('a');
    element.setAttribute('href', 'data:text/csv;charset=utf-8,' + encodeURIComponent(csvString));
    element.setAttribute('download', `${data.author}_data.csv`);
    element.style.display = 'none';
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
  };

  return (
    <div className="explorer-container">
      {/* Header */}
      <header className="explorer-header">
        <div className="header-left">
          <i className='bx bxs-graduation'></i>
          <h1 className="logo">Acade Mine</h1>
        </div>
        <div className="header-right">
          <nav className="header-nav">
            <a href="#dashboard" onClick={onBack} className="nav-link">Dashboard</a>
            <a href="#settings" className="nav-link">Settings</a>
            <a href="#about" onClick={onNavigateToAbout} className="nav-link">About Us</a>
            <button className="nav-link logout-btn" onClick={onLogout}>Logout</button>
          </nav>
          <div className="user-icon" onClick={onNavigateToProfile}>
            <i className='bx bxs-user-circle'></i>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="explorer-main">
        <h1 className="page-title">Data Explorer</h1>

        {/* Author Profile Section */}
        {data && (
          <section className="author-profile">
            <div className="profile-left">
              <div className="avatar">
                <i className='bx bxs-user-circle'></i>
              </div>
              <div className="profile-info">
                <h2>{data.author}</h2>
                <p>{data.email}</p>
              </div>
            </div>

            <div className="profile-right">
              <div className="metrics-grid">
                <div className="metric-box">
                  <span className="metric-label">Total Publications</span>
                  <span className="metric-value">{data.totalPublications}</span>
                </div>
                <div className="metric-box">
                  <span className="metric-label">Total Citations</span>
                  <span className="metric-value">{data.totalCitations}</span>
                </div>
                <div className="metric-box">
                  <span className="metric-label">Total Self Citations</span>
                  <span className="metric-value">{data.totalSelfCitations}</span>
                </div>
                <div className="metric-box">
                  <span className="metric-label">Nm Index</span>
                  <span className="metric-value">{data.nmIndex}</span>
                </div>
                <div className="metric-box">
                  <span className="metric-label">H Index</span>
                  <span className="metric-value">{data.hIndex}</span>
                </div>
                <div className="metric-box">
                  <span className="metric-label">C Score</span>
                  <span className="metric-value">{data.cScore}</span>
                </div>
              </div>
            </div>

            <div className="chart-placeholder">
              <p>📊 Trends Chart</p>
            </div>
          </section>
        )}

        {error && <div className="error-message">{error}</div>}

        {/* Filter Section */}
        {data && (
          <section className="filter-section">
            <div className="filter-header">
              <i className='bx bx-filter-alt'></i>
              <span>Filter</span>
            </div>
            <div className="filter-controls">
              <div className="filter-group">
                <label>Field</label>
                <select value={selectedField} onChange={(e) => setSelectedField(e.target.value)}>
                  <option value="">Select Field</option>
                  <option value="cs">Computer Science</option>
                  <option value="bio">Biology</option>
                  <option value="phys">Physics</option>
                </select>
              </div>
              <div className="filter-group">
                <label>Year</label>
                <select value={selectedYear} onChange={(e) => setSelectedYear(e.target.value)}>
                  <option value="">Select Year</option>
                  <option value="2024">2024</option>
                  <option value="2023">2023</option>
                  <option value="2022">2022</option>
                </select>
              </div>
              <div className="filter-group">
                <label>H-Index</label>
                <select value={selectedHIndex} onChange={(e) => setSelectedHIndex(e.target.value)}>
                  <option value="">H-Index</option>
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </select>
              </div>
              <div className="filter-group">
                <label>Nm-Index</label>
                <select value={selectedNmIndex} onChange={(e) => setSelectedNmIndex(e.target.value)}>
                  <option value="">Nm-Index</option>
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </select>
              </div>
            </div>
          </section>
        )}

        {/* Publications Section */}
        {data && (
          <section className="publications-section">
            {data.publications.map((pub) => (
              <div key={pub.id} className="publication-card">
                <div className="pub-header">
                  <h3>{pub.title}</h3>
                  <div className="pub-metrics-right">
                    <div className="metric">
                      <span className="label">Total Self Citations</span>
                      <span className="value">{pub.selfCitations}</span>
                    </div>
                    <div className="metric">
                      <span className="label">Published Year</span>
                      <span className="value">{pub.publishedYear}</span>
                    </div>
                    <div className="metric">
                      <span className="label">Total Citations</span>
                      <span className="value">{pub.totalCitations}</span>
                    </div>
                  </div>
                </div>

                <div className="pub-fields">
                  {pub.fields.map((field, idx) => (
                    <span key={idx} className="field-tag">{field}</span>
                  ))}
                </div>

                <div className="pub-authors">
                  <h4>Authors Contribution</h4>
                  <ul>
                    {pub.authors.map((author, idx) => (
                      <li key={idx}>{author}</li>
                    ))}
                  </ul>
                </div>
              </div>
            ))}
          </section>
        )}

        {/* Export Button */}
        {data && (
          <div className="export-section">
            <button className="export-btn" onClick={handleExportCSV}>
              Click here to Export CSV
            </button>
          </div>
        )}

        {!data && !loading && (
          <div className="placeholder-message">
            <p>Search for an author to explore their research profile</p>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="explorer-footer">
        <div className="footer-content">
          <div className="footer-section">
            <h4>Acade Mine</h4>
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
              <li><a href="#email">info@academine.edu</a></li>
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
