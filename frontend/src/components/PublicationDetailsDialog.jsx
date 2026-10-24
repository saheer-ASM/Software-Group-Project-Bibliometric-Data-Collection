import React, { useEffect, useRef, useState } from 'react';
import { API_BASE_URL, authHeaders } from '../config/api';
import PublicationCard from './PublicationCard';

/**
 * A saved publication opened from My Library. It is the Data Explorer's own
 * publication card, loaded from the same endpoint the Data Explorer pages
 * through (narrowed to this one publication), shown in the Data Explorer's
 * modal shell -- so the details and interactions match exactly.
 *
 * The record is loaded for the author the paper was saved from: the card's
 * author-specific figures (contribution, self and adjusted citations) belong
 * to that author, as they did where the paper was saved.
 */
export default function PublicationDetailsDialog({
  paper,
  collectionName,
  saved,
  onToggleSave,
  onSelectAuthor,
  onClose,
}) {
  const [publication, setPublication] = useState(null);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  const [expanded, setExpanded] = useState(false);
  const closeRef = useRef(null);

  useEffect(() => {
    closeRef.current?.focus();
    const onKeyDown = (event) => { if (event.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [onClose]);

  useEffect(() => {
    setPublication(null);
    setError('');
    if (!paper.authorId) {
      setError('This publication was saved without the author it came from, so its details cannot be loaded here. Open it from the author’s profile and save it again.');
      return undefined;
    }
    const controller = new AbortController();
    const params = new URLSearchParams({ authorId: paper.authorId, pubId: paper.id });
    fetch(`${API_BASE_URL}/api/search/publications?${params.toString()}`, { signal: controller.signal, headers: authHeaders() })
      .then(async (response) => {
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(payload.message || 'Could not load this publication.');
        const [record] = payload.publications || [];
        if (!record) throw new Error('This publication is no longer available in the NmIndex database.');
        setPublication(record);
      })
      .catch((err) => {
        if (err.name !== 'AbortError') setError(err.message || 'Could not load this publication.');
      });
    return () => controller.abort();
  }, [paper.id, paper.authorId, attempt]);

  return (
    <div className="de-collection-modal de-publication-modal" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <div className="de-collection-dialog de-publication-dialog" role="dialog" aria-modal="true" aria-labelledby="publication-dialog-title">
        <div className="de-collection-dialog-header">
          <span><i className="bx bx-file"></i></span>
          <div>
            <small>SAVED PUBLICATION</small>
            <h2 id="publication-dialog-title">Publication details</h2>
          </div>
          <button type="button" aria-label="Close" ref={closeRef} onClick={onClose}><i className="bx bx-x"></i></button>
        </div>
        <div className="de-publication-dialog-body">
        {paper.authorName && (
          <p className="de-publication-dialog-context">
            Contribution and citation figures are for <strong>{paper.authorName}</strong>, whose profile it was saved from.
          </p>
        )}
        {!publication && !error && (
          <p className="de-publication-dialog-status" role="status">
            <i className="bx bx-loader-alt bx-spin" aria-hidden="true"></i> Loading publication&hellip;
          </p>
        )}
        {error && (
          <div className="de-publication-dialog-status">
            <p className="de-save-notice" role="alert">{error}</p>
            {paper.authorId && <button type="button" className="de-publication-dialog-retry" onClick={() => setAttempt((n) => n + 1)}>Try again</button>}
          </div>
        )}
        {publication && (
          <PublicationCard
            publication={publication}
            label={collectionName || 'Saved publication'}
            saved={saved}
            onToggleSave={onToggleSave}
            expanded={expanded}
            onToggleExpanded={() => setExpanded((value) => !value)}
            onSelectAuthor={onSelectAuthor}
          />
        )}
        </div>
      </div>
    </div>
  );
}
