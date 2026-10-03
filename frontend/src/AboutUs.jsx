import React from 'react';
import './AboutUs.css';
import AppNavbar from './AppNavbar';
import { FooterQuickLinks, FooterContactLinks, FooterCopyright } from './FooterParts';

const AboutUs = ({ onBack, onNavigateToSettings, onNavigateToProfile, onNavigateToLibrary, onLogout, hasSearchedAuthor, onNavigateToExplorer }) => {
  const teamMembers = [
    {
      name: 'Ahamed R.S.',
      github: 'https://github.com/Shaith-Ahamed',
      linkedin: 'https://www.linkedin.com/in/r-shaith-ahamed-5273b1240',
      email: 'shaith1208@gmail.com',
    },
    {
      name: 'Ahnaf M.N.M.',
      github: 'https://github.com/mohomad-ahnaf',
      linkedin: 'https://www.linkedin.com/in/mohomad-ahnaf',
      email: 'ahnafmnm01@gmail.com',
    },
    {
      name: 'Saheer A.S.M',
      github: 'https://github.com/saheer-ASM',
      linkedin: 'https://www.linkedin.com/in/mohomed-saheer-5ba903278',
      email: 'mohamedshaheer637@gmail.com',
    },
    {
      name: 'Thurga R.',
      github: 'https://github.com/Thurga1125',
      linkedin: 'https://www.linkedin.com/in/thurgarajinathan25',
      email: 'thurga11252001@gmail.com',
    },
  ];

  // Same for every member
  const memberDetails = [
    'B.Sc.Eng. (Hons) in Computer Engineering (Reading)',
    'Department of Electrical and Information Engineering',
    'University of Ruhuna',
  ];

  return (
    <div className="about-container">
      <AppNavbar activePage="about" onDashboard={onBack} onExplorer={onNavigateToExplorer} onLibrary={onNavigateToLibrary} onAbout={() => {}} onProfile={onNavigateToProfile} onLogout={onLogout} />

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
            <div className="member-socials advisor-socials">
              <a href="https://www.linkedin.com/in/shehan-nilmantha-wijesekara-86a9931a3" target="_blank" rel="noopener noreferrer" aria-label="Dr. P.A.D.S. Nilmantha Wijesekara on LinkedIn" title="LinkedIn">
                <i className="bx bxl-linkedin" aria-hidden="true"></i>
              </a>
              <a href="mailto:nilmantha@eie.ruh.ac.lk" aria-label="Email Dr. P.A.D.S. Nilmantha Wijesekara" title="nilmantha@eie.ruh.ac.lk">
                <i className="bx bx-envelope" aria-hidden="true"></i>
              </a>
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
                <div className="member-socials">
                  <a href={member.github} target="_blank" rel="noopener noreferrer" aria-label={`${member.name} on GitHub`} title="GitHub">
                    <i className="bx bxl-github" aria-hidden="true"></i>
                  </a>
                  <a href={member.linkedin} target="_blank" rel="noopener noreferrer" aria-label={`${member.name} on LinkedIn`} title="LinkedIn">
                    <i className="bx bxl-linkedin" aria-hidden="true"></i>
                  </a>
                  <a href={`mailto:${member.email}`} aria-label={`Email ${member.name}`} title={member.email}>
                    <i className="bx bx-envelope" aria-hidden="true"></i>
                  </a>
                </div>
                <div className="member-details">
                  {memberDetails.map((line) => (
                    <p key={line}>{line}</p>
                  ))}
                </div>
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
              <FooterQuickLinks />
            </ul>
          </div>


          <div className="footer-section">
            <h4>Contact</h4>
            <ul>
              <FooterContactLinks />
            </ul>
          </div>
        </div>
        <FooterCopyright />
      </footer>
    </div>
  );
};

export default AboutUs;
