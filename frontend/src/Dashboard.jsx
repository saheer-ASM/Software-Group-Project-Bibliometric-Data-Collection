
import React, { useState, useRef } from 'react';
import './Dashboard.css';

const Dashboard = ({ username = "User", onLogout, onNavigateToExplorer, onNavigateToSettings, onNavigateToAbout, onNavigateToProfile, hasSearchedAuthor, onResetSearch }) => {
  const [searchQuery, setSearchQuery] = useState('');
  const scrollContainerRef = useRef(null);

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

  // Sample data
  const stats = {
    publications: '1025828',
    authors: '24852+',
    fields: '341'
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
      // Navigate to Data Explorer with author name
      onNavigateToExplorer(searchQuery);
    }
  };

  const handleFieldClick = (fieldName) => {
    console.log('Field clicked:', fieldName);
    // Add navigation logic here
  };

  return (
    <div className="dashboard-container">
      {/* Header */}
      <header className="dashboard-header">
        <div className="header-left">
          <i className='bx bxs-graduation'></i>
          <h1 className="logo">ScholarMetrics</h1>
        </div>
        <div className="header-right">
          <nav className="header-nav">
            <a href="#dashboard" className="nav-link active">Dashboard</a>
            {hasSearchedAuthor && (
              <a href="#explorer" className="nav-link" onClick={(e) => { e.preventDefault(); onNavigateToExplorer(searchQuery || 'Researcher'); }}>Data Explorer</a>
            )}
            <a href="#about" className="nav-link" onClick={onNavigateToAbout}>About Us</a>
            <button className="nav-link logout-btn" onClick={onLogout}>Logout</button>
          </nav>
          <div className="user-icon" onClick={onNavigateToProfile}>
            <i className='bx bxs-user-circle'></i>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="dashboard-main">
        {/* Welcome Section */}
        <div className="welcome-section">
          <h2>Welcome {username}!</h2>
        </div>

        {/* Quick Stats */}
        <section className="stats-section">
          <h2 className="section-title">Quick States</h2>
          <div className="stats-grid">
            <div className="stat-card">
              <div className="stat-number">{stats.publications}</div>
              <div className="stat-label">Publications</div>
            </div>
            <div className="stat-card highlight">
              <div className="stat-number">{stats.authors}</div>
              <div className="stat-label">Authors</div>
            </div>
            <div className="stat-card">
              <div className="stat-number">{stats.fields}</div>
              <div className="stat-label">Fields</div>
            </div>
          </div>
        </section>

        {/* Author Search */}
        <section className="search-section">
          <h2 className="section-title">Author Search</h2>
          <form onSubmit={handleSearch} className="search-form">
            <input
              type="text"
              placeholder="Enter Author's Name"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="search-input"
            />
            <button type="submit" className="search-btn">
              <i className='bx bx-search'></i>
            </button>
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