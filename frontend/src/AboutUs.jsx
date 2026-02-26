import React from 'react';
import './AboutUs.css';

const AboutUs = ({ onBack, onNavigateToSettings, onNavigateToProfile, onLogout, hasSearchedAuthor, onNavigateToExplorer }) => {
  const teamMembers = [
    { name: 'Ahamed R.S.', id: 'EG/2022/4919' },
    { name: 'Ahnaf M.N.M.', id: 'EG/2022/4920' },
    { name: 'Saheer A.S.M', id: 'EG/2022/5304' },
    { name: 'Thurga R.', id: 'EG/2022/5374' }
  ];

  return (
    <div className="about-container">
      {/* Header */}
      <header className="about-header">
        <div className="header-left">
          <i className='bx bxs-graduation'></i>
          <h1 className="logo">ScholarMetrics</h1>
        </div>
        <div className="header-right">
          <nav className="header-nav">
            <a href="#dashboard" onClick={onBack} className="nav-link">Dashboard</a>
            {hasSearchedAuthor && (
              <a href="#explorer" className="nav-link" onClick={(e) => { e.preventDefault(); onNavigateToExplorer(''); }}>Data Explorer</a>
            )}
            <a href="#about" className="nav-link active">About Us</a>
            <a href="#logout" className="nav-link" onClick={onLogout}>Logout</a>
          </nav>
          <div className="user-icon" onClick={onNavigateToProfile}>
            <i className='bx bxs-user-circle'></i>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="about-main">
        {/* Page Title */}
        <section className="title-section">
          <h1 className="page-title">About ScholarMetrics</h1>
          <p className="subtitle">
            Automated Bibliometric Data Gathering System - Revolutionizing research evaluation
            through intelligent automation and comprehensive data collection across global scholarly
            databases.
          </p>
        </section>

        {/* Our Mission */}
        <section className="mission-section">
          <h2 className="section-title">Our Mission</h2>
          <div className="mission-cards">
            <div className="mission-card">
              <h3>Scale Research Evaluation</h3>
              <p>
                Enable large-scale bibliometric analysis of 100,000 researchers across
                12 scientific disciplines efficiently and accurately.
              </p>
            </div>
            <div className="mission-card">
              <h3>Automate Data Collection</h3>
              <p>
                Transform months of manual work into automated processes, eliminating
                human error and saving valuable research time.
              </p>
            </div>
            <div className="mission-card">
              <h3>Provide Actionable Insights</h3>
              <p>
                Deliver comprehensive CSV exports with citation metrics, h-index
                calculations, and author contribution analysis for data-driven decisions.
              </p>
            </div>
          </div>
        </section>

        {/* Our Team */}
        <section className="team-section">
          <h2 className="section-title">Our Team</h2>
          
          {/* Project Advisor */}
          <div className="advisor-card">
            <h3 className="advisor-title">Project Advisor</h3>
            <h2 className="advisor-name">Dr. P.A.D.S. Nilmantha Wijesekara</h2>
            <p className="advisor-credentials">
              Ph.D. (Ruhuna), B.Sc.Engineering (First-Class Honors, Ruhuna), AMIE (SL)
            </p>
            <p className="advisor-position">
              Lecturer, Department of Electrical and Information Engineering,
              Faculty of Engineering, University of Ruhuna.
            </p>
            <div className="advisor-links">
              <a href="#dbie" className="link-item">DBIE</a>
              <a href="#researchgate" className="link-item">ResearchGate</a>
              <a href="#scholar" className="link-item">Google_Scholar</a>
              <a href="#scopus" className="link-item">Scopus</a>
              <a href="#wos" className="link-item">WoS</a>
              <a href="#orcid" className="link-item">ORCID</a>
            </div>
          </div>

          {/* Team Members */}
          <div className="members-grid">
            {teamMembers.map((member, index) => (
              <div key={index} className="member-card">
                <div className="member-icon">
                  <i className='bx bxs-user'></i>
                </div>
                <h3 className="member-name">{member.name}</h3>
                <p className="member-id">{member.id}</p>
              </div>
            ))}
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="about-footer">
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

export default AboutUs;