import React from 'react';
import { useLocation } from 'react-router-dom';
import { useAppShell } from './appShell';
import './AppNavbar.css';

// The active item follows the current URL (falls back to the page's activePage prop).
const ACTIVE_BY_PATH = {
  '/dashboard': 'dashboard',
  '/data-explorer': 'explorer',
  '/library': 'library',
  '/about': 'about',
  '/admin': 'admin',
  '/settings': 'profile',
};

export default function AppNavbar({ activePage, onDashboard, onExplorer, onLibrary, onAbout, onProfile, onLogout }) {
  // Shown only to users whose token has the admin claim; Firestore rules enforce access.
  const { isAdmin, goTo } = useAppShell();
  const { pathname } = useLocation();
  const current = ACTIVE_BY_PATH[pathname] || activePage;

  // Real hrefs (so "open in new tab" / copy link work); normal clicks are handled
  // in-app by the router without a page reload.
  const link = (page, label, href, handler) => (
    <a
      href={href}
      className={`app-nav-link${current === page ? ' active' : ''}`}
      aria-current={current === page ? 'page' : undefined}
      onClick={(event) => { event.preventDefault(); handler?.(event); }}
    >
      {label}
    </a>
  );
  return <header className="app-navbar">
    <button className="app-nav-brand" onClick={onDashboard}><i className="bx bxs-graduation"></i><span>ScholarMetrics</span></button>
    <div className="app-nav-right">
      <nav aria-label="Main navigation">
        {link('dashboard', 'Dashboard', '/dashboard', onDashboard)}
        {link('explorer', 'Data Explorer', '/data-explorer', () => onExplorer?.(''))}
        {link('library', 'My Library', '/library', onLibrary)}
        {link('about', 'About Us', '/about', onAbout)}
        {isAdmin && link('admin', 'Admin', '/admin', () => goTo('admin'))}
        <button className="app-nav-link app-nav-logout" onClick={onLogout}>Logout</button>
      </nav>
      <button
        className={`app-nav-profile${current === 'profile' ? ' active' : ''}`}
        onClick={onProfile}
        aria-label="Open profile settings"
        aria-current={current === 'profile' ? 'page' : undefined}
      >
        <i className="bx bxs-user-circle"></i>
      </button>
    </div>
  </header>;
}
