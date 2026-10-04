import React, { useEffect, useState } from 'react';
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

  // Mobile only: the icon rail under the header expands into a labelled sidebar.
  // Desktop ignores this entirely -- the rail and the toggle are display:none there.
  const [menuOpen, setMenuOpen] = useState(false);

  // A route change means the user picked something; close the sidebar behind them.
  useEffect(() => { setMenuOpen(false); }, [pathname]);

  useEffect(() => {
    if (!menuOpen) return undefined;
    const onKey = (event) => { if (event.key === 'Escape') setMenuOpen(false); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [menuOpen]);

  // Real hrefs (so "open in new tab" / copy link work); normal clicks are handled
  // in-app by the router without a page reload.
  const link = (page, label, href, handler, icon) => (
    <a
      href={href}
      className={`app-nav-link${current === page ? ' active' : ''}`}
      aria-current={current === page ? 'page' : undefined}
      onClick={(event) => { event.preventDefault(); setMenuOpen(false); handler?.(event); }}
    >
      <i className={`bx ${icon}`} aria-hidden="true" />
      <span className="app-nav-label">{label}</span>
    </a>
  );

  return <header className={`app-navbar${menuOpen ? ' menu-open' : ''}`}>
    <button
      className="app-nav-toggle"
      onClick={() => setMenuOpen((open) => !open)}
      aria-label={menuOpen ? 'Close navigation menu' : 'Open navigation menu'}
      aria-expanded={menuOpen}
      aria-controls="app-nav-menu"
    >
      <i className={`bx ${menuOpen ? 'bx-x' : 'bx-menu'}`} aria-hidden="true" />
    </button>

    <button className="app-nav-brand" onClick={onDashboard} aria-label="NmIndex home">
      <img src="/assets/nmindex-header.png" alt="NmIndex — Researcher Impact Analytics" className="app-nav-logo" />
    </button>

    <div className="app-nav-right">
      <nav id="app-nav-menu" className={`app-nav-menu${menuOpen ? ' open' : ''}`} aria-label="Main navigation">
        {link('dashboard', 'Dashboard', '/dashboard', onDashboard, 'bxs-dashboard')}
        {link('explorer', 'Data Explorer', '/data-explorer', () => onExplorer?.(''), 'bx-search-alt')}
        {link('library', 'My Library', '/library', onLibrary, 'bxs-book-bookmark')}
        {link('about', 'About Us', '/about', onAbout, 'bx-info-circle')}
        {isAdmin && link('admin', 'Admin', '/admin', () => goTo('admin'), 'bxs-shield')}
        <button
          className="app-nav-link app-nav-logout"
          onClick={() => { setMenuOpen(false); onLogout?.(); }}
        >
          <i className="bx bx-log-out" aria-hidden="true" />
          <span className="app-nav-label">Logout</span>
        </button>
      </nav>

      {/* Stays in the top-right on every size, exactly as before. */}
      <button
        className={`app-nav-profile${current === 'profile' ? ' active' : ''}`}
        onClick={onProfile}
        aria-label="Open profile settings"
        aria-current={current === 'profile' ? 'page' : undefined}
      >
        <i className="bx bxs-user-circle"></i>
      </button>
    </div>

    {/* Tap-anywhere-else to dismiss. Mobile only; display:none on desktop. */}
    <button
      className="app-nav-backdrop"
      hidden={!menuOpen}
      aria-hidden="true"
      tabIndex={-1}
      onClick={() => setMenuOpen(false)}
    />
  </header>;
}
