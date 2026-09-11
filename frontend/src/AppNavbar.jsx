import React from 'react';
import './AppNavbar.css';

export default function AppNavbar({ activePage, onDashboard, onExplorer, onLibrary, onAbout, onProfile, onLogout }) {
  const link = (page, label, href, handler) => <a href={href} className={`app-nav-link${activePage === page ? ' active' : ''}`} onClick={(event) => { event.preventDefault(); handler?.(event); }}>{label}</a>;
  return <header className="app-navbar">
    <button className="app-nav-brand" onClick={onDashboard}><i className="bx bxs-graduation"></i><span>ScholarMetrics</span></button>
    <div className="app-nav-right">
      <nav aria-label="Main navigation">
        {link('dashboard', 'Dashboard', '#dashboard', onDashboard)}
        {link('explorer', 'Data Explorer', '#explorer', () => onExplorer?.(''))}
        {link('library', 'My Library', '#library', onLibrary)}
        {link('about', 'About Us', '#about', onAbout)}
        <button className="app-nav-link app-nav-logout" onClick={onLogout}>Logout</button>
      </nav>
      <button className={`app-nav-profile${activePage === 'profile' ? ' active' : ''}`} onClick={onProfile} aria-label="Open profile"><i className="bx bxs-user-circle"></i></button>
    </div>
  </header>;
}
