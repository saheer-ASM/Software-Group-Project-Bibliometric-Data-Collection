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

// Scrolls the window, which is what every page uses -- none of them put the
// content in its own overflow container.
//
// The animation is done by hand rather than with `behavior: 'smooth'`, which
// is a SILENT no-op in this app: index.css sets `overflow-x: clip` on
// html/body (a deliberate guard against sideways scroll), and Chromium will
// not animate the document scroll of a clipped scroller. Measured from a
// scroll position of 2494px, eight samples over 3.2s never moved, while an
// instant scrollTo(0,0) worked immediately.
export const BackToTop = () => {
  const scrollToTop = () => {
    const start = window.scrollY || document.documentElement.scrollTop || 0;
    const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

    if (start === 0) return;

    // requestAnimationFrame never fires while the document is hidden, so an
    // animation started in a background tab would freeze part-way. Jump
    // straight to the top in that case (and when motion is reduced).
    if (reduceMotion || document.hidden) {
      window.scrollTo(0, 0);
      return;
    }

    const duration = Math.min(600, Math.max(250, start * 0.35));
    const startedAt = performance.now();
    const easeOutCubic = (t) => 1 - (1 - t) ** 3;

    const step = (now) => {
      const progress = Math.min(1, (now - startedAt) / duration);
      window.scrollTo(0, Math.round(start * (1 - easeOutCubic(progress))));
      if (progress < 1) requestAnimationFrame(step);
    };

    requestAnimationFrame(step);
  };

  return (
    <button type="button" className="footer-back-to-top" onClick={scrollToTop}>
      Back to top
      <i className="bx bx-up-arrow-alt" aria-hidden="true" />
    </button>
  );
};

// Rendered by all seven page footers, so the button only needs adding here.
export const FooterCopyright = () => (
  <div className="footer-copyright">
    <BackToTop />
    <div className="footer-copyright-text">
      © {new Date().getFullYear()} NmIndex. All rights reserved.
    </div>
  </div>
);
