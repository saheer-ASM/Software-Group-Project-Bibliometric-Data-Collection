import React from 'react';
import { useAppShell } from './appShell';
import './FooterParts.css';

// Pieces shared by every page footer (Dashboard, Data Explorer, About Us,
// Profile, Settings). Each page keeps its own footer layout and styling; these
// only supply the links, so they behave the same everywhere.

export const CONTACT_EMAIL = 'info@academine.edu';

// In-app navigation: real paths (no host, no localhost) so links can be opened
// in a new tab; normal clicks are handled by the router without a reload.
const action = (handler) => (event) => {
  event.preventDefault();
  handler();
};

export const FooterQuickLinks = () => {
  const { goTo } = useAppShell();
  return (
    <>
      <li><a href="/dashboard" onClick={action(() => goTo('dashboard'))}>Dashboard</a></li>
      <li><a href="/data-explorer" onClick={action(() => goTo('explorer'))}>Data Explorer</a></li>
      <li><a href="/settings" onClick={action(() => goTo('settings'))}>Settings</a></li>
      <li><a href="/about" onClick={action(() => goTo('about'))}>About Us</a></li>
    </>
  );
};

export const FooterContactLinks = () => {
  const { openSupport } = useAppShell();
  return (
    <>
      <li><a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a></li>
      <li><a href="#send-feedback" role="button" onClick={action(() => openSupport('feedback'))}>Send Feedback</a></li>
      <li><a href="#report-issue" role="button" onClick={action(() => openSupport('issue'))}>Report an Issue</a></li>
    </>
  );
};

export const FooterCopyright = () => (
  <div className="footer-copyright">
    © {new Date().getFullYear()} ScholarMetrics. All rights reserved.
  </div>
);
