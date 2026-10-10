import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  getLibrary, saveLibrary, removeSavedAuthor, removeRecentAuthor, clearRecentAuthors,
  removeSavedPaper, savePaperToCollection,
  MAX_SAVED_AUTHORS, MAX_SAVED_PAPERS, RECENT_AUTHORS_PREVIEW, RECENT_RETENTION_DAYS,
} from './services/researchLibrary';
import PublicationDetailsDialog from './components/PublicationDetailsDialog';
import './Dashboard.css';
import './Library.css';
import AppNavbar from './AppNavbar';
import { FooterQuickLinks, FooterContactLinks, FooterCopyright } from './FooterParts';

export default function Library({ user, onBack, onOpenAuthor, onNavigateToAbout, onNavigateToProfile, onLogout, hasSearchedAuthor }) {
  const userId = user?.id || user?.email;
  const [library, setLibrary] = useState(() => getLibrary(userId));
  const [collectionName, setCollectionName] = useState('');
  const [activeCollection, setActiveCollection] = useState('all');
  const [pendingDeleteId, setPendingDeleteId] = useState(null);
  const [showFullHistory, setShowFullHistory] = useState(false);
  const [confirmClearHistory, setConfirmClearHistory] = useState(false);
  // An action the server refused or that failed offline; the list itself has
  // already been put back by the service.
  const [notice, setNotice] = useState('');
  // The saved paper whose details are open, with the collection it was in when
  // opened (so removing and re-saving it from the dialog puts it back there).
  const [openPaper, setOpenPaper] = useState(null);
  const paperTriggerRef = useRef(null);

  useEffect(() => {
    const sync = (event) => setLibrary(event.detail || getLibrary(userId));
    window.addEventListener('research-library-changed', sync);
    return () => window.removeEventListener('research-library-changed', sync);
  }, [userId]);

  const persist = (next) => { setLibrary(next); saveLibrary(userId, next); };
  const createCollection = (event) => {
    event.preventDefault();
    const name = collectionName.trim();
    if (!name) return;
    persist({ ...library, collections: [...library.collections, { id: Date.now().toString(), name, paperIds: [] }] });
    setCollectionName('');
  };
  const assignPaper = (paperId, collectionId) => persist({
    ...library,
    collections: library.collections.map((collection) => ({
      ...collection,
      paperIds: collection.id === collectionId
        ? [...new Set([...collection.paperIds, paperId])]
        : collection.paperIds.filter((id) => id !== paperId)
    }))
  });
  // Deletes the grouping only -- every publication stays in savedPapers, so
  // nothing the user bookmarked is lost.
  const deleteCollection = (collectionId) => {
    persist({ ...library, collections: library.collections.filter((collection) => collection.id !== collectionId) });
    if (activeCollection === collectionId) setActiveCollection('all');
    setPendingDeleteId(null);
  };
  const report = (result) => setNotice(result && !result.ok ? result.message : '');
  const handleRemoveSavedAuthor = (authorId) => removeSavedAuthor(userId, authorId).then(report);
  const handleRemoveRecentAuthor = (authorId) => removeRecentAuthor(userId, authorId).then(report);
  const handleClearHistory = () => {
    setConfirmClearHistory(false);
    setShowFullHistory(false);
    clearRecentAuthors(userId).then(report);
  };
  // Opened by id as well as name: several researchers share a name, and the
  // name alone would open whichever one the database returned first.
  const openAuthor = (author) => onOpenAuthor({ id: author.id, name: author.name });
  const collectionOfPaper = (paperId) => library.collections.find((collection) => collection.paperIds.includes(paperId));
  const openPaperDetails = (paper, trigger) => {
    paperTriggerRef.current = trigger;
    const collection = collectionOfPaper(paper.id);
    setOpenPaper({ paper, collectionId: collection?.id || '', collectionName: collection?.name || '' });
  };
  // Closing leaves the active collection and scroll position as they were, and
  // returns focus to the paper that was opened (when it is still listed).
  const closePaperDetails = useCallback(() => {
    setOpenPaper(null);
    const trigger = paperTriggerRef.current;
    if (trigger && document.contains(trigger)) trigger.focus();
  }, []);
  const handleRemovePaper = (paperId) => removeSavedPaper(userId, paperId).then(report);
  // The card's Saved / Save paper button, as in the Data Explorer: removes the
  // paper, or saves it again into the collection it came from.
  const toggleOpenPaperSaved = () => {
    if (!openPaper) return;
    const isSaved = library.savedPapers.some((paper) => paper.id === openPaper.paper.id);
    (isSaved
      ? removeSavedPaper(userId, openPaper.paper.id)
      : savePaperToCollection(userId, openPaper.paper, openPaper.collectionId, '')
    ).then(report);
  };
  const visibleRecentAuthors = showFullHistory
    ? library.recentAuthors
    : library.recentAuthors.slice(0, RECENT_AUTHORS_PREVIEW);
  const pendingDelete = library.collections.find((collection) => collection.id === pendingDeleteId) || null;
  const visiblePapers = activeCollection === 'all'
    ? library.savedPapers
    : library.savedPapers.filter((paper) => library.collections.find((collection) => collection.id === activeCollection)?.paperIds.includes(paper.id));

  return <div className="library-page">
    <AppNavbar activePage="library" onDashboard={onBack} onExplorer={onOpenAuthor} onLibrary={() => {}} onAbout={onNavigateToAbout} onProfile={onNavigateToProfile} onLogout={onLogout} />
    <main className="library-main">
      <section className="library-intro">
        <div className="library-intro-copy"><span>PERSONAL WORKSPACE</span><h2>Your research, ready when you are</h2><p>Keep important researchers and publications together, revisit recent profiles, and organize papers into focused collections.</p>
          <div className="library-overview"><div><strong>{library.savedAuthors.length}</strong><small>Saved authors</small></div><div><strong>{library.savedPapers.length}</strong><small>Saved papers</small></div><div><strong>{library.collections.length}</strong><small>Collections</small></div></div>
        </div>
        <div className="library-intro-art"><span><i className="bx bx-bookmark-heart"></i></span><i className="bx bx-book-open"></i></div>
      </section>
      {notice && <p className="library-notice" role="alert">{notice}</p>}
      <div className="library-grid">
        <section className="library-panel"><h2><i className="bx bxs-user-pin" /> Saved authors <small aria-label={`${library.savedAuthors.length} of ${MAX_SAVED_AUTHORS} saved`}>({library.savedAuthors.length}/{MAX_SAVED_AUTHORS})</small></h2>
          <div className="library-items">{library.savedAuthors.length ? library.savedAuthors.map((author) => <div className="library-author-row" key={author.id}><button className="library-author-open" onClick={() => openAuthor(author)}><i className="bx bxs-user-circle" /><span><strong>{author.name}</strong><small>{author.id}</small></span><i className="bx bx-chevron-right" /></button><button className="library-author-delete" onClick={() => handleRemoveSavedAuthor(author.id)} aria-label={`Remove ${author.name} from saved authors`} title="Remove saved author"><i className="bx bx-trash" /></button></div>) : <p className="library-empty">Save an author from their Data Explorer profile.</p>}</div>
        </section>
        <section className="library-panel"><h2><i className="bx bx-history" /> Recently viewed <small>{library.recentAuthors.length}</small></h2>
          <div className="library-items">{library.recentAuthors.length ? visibleRecentAuthors.map((author) => <div className="library-author-row" key={author.id}><button className="library-author-open" onClick={() => openAuthor(author)}><i className="bx bx-time-five" /><span><strong>{author.name}</strong><small>{new Date(author.viewedAt).toLocaleDateString()}</small></span><i className="bx bx-chevron-right" /></button><button className="library-author-delete" onClick={() => handleRemoveRecentAuthor(author.id)} aria-label={`Remove ${author.name} from recently viewed`} title="Remove recent author"><i className="bx bx-trash" /></button></div>) : <p className="library-empty">Viewed researchers will appear here.</p>}</div>
          {library.recentAuthors.length > 0 && (confirmClearHistory
            ? <div className="library-collection-confirm" role="alert">
              <span>Clear your browsing history? Saved authors are not affected.</span>
              <button type="button" className="library-confirm-delete" onClick={handleClearHistory}>Clear</button>
              <button type="button" className="library-confirm-cancel" onClick={() => setConfirmClearHistory(false)}>Cancel</button>
            </div>
            : <div className="library-panel-actions">
              <span>
                {showFullHistory || library.recentAuthors.length <= RECENT_AUTHORS_PREVIEW
                  ? `Last ${RECENT_RETENTION_DAYS} days`
                  : `Latest ${RECENT_AUTHORS_PREVIEW} of ${library.recentAuthors.length}`}
              </span>
              {library.recentAuthors.length > RECENT_AUTHORS_PREVIEW && (
                <button type="button" onClick={() => setShowFullHistory((value) => !value)} aria-expanded={showFullHistory}>
                  {showFullHistory ? 'Show latest' : `Full history (${library.recentAuthors.length})`}
                </button>
              )}
              <button type="button" className="library-clear-history" onClick={() => setConfirmClearHistory(true)}>Clear history</button>
            </div>)}
        </section>
      </div>
      <section className="library-panel library-papers"><div className="library-panel-title"><h2><i className="bx bx-file" /> Saved publications <small aria-label={`${library.savedPapers.length} of ${MAX_SAVED_PAPERS} saved`}>({library.savedPapers.length}/{MAX_SAVED_PAPERS})</small></h2><form onSubmit={createCollection}><input value={collectionName} onChange={(e) => setCollectionName(e.target.value)} placeholder="New collection name" /><button>Create collection</button></form></div>
        <div className="library-collections" role="group" aria-label="Filter publications by collection">
          <button className={activeCollection === 'all' ? 'active' : ''} onClick={() => setActiveCollection('all')}>All <strong>{library.savedPapers.length}</strong></button>
          {library.collections.map((collection) => <span key={collection.id} className="library-collection-chip">
            <button className={activeCollection === collection.id ? 'active' : ''} onClick={() => setActiveCollection(collection.id)}>{collection.name} <strong>{collection.paperIds.length}</strong></button>
            <button type="button" className="library-collection-delete" aria-label={`Delete collection ${collection.name}`} onClick={() => setPendingDeleteId(collection.id)}><i className="bx bx-x" aria-hidden="true" /></button>
          </span>)}
        </div>
        {pendingDelete && <div className="library-collection-confirm" role="alert">
          <span>Delete &ldquo;{pendingDelete.name}&rdquo;? {pendingDelete.paperIds.length
            ? `Its ${pendingDelete.paperIds.length} publication${pendingDelete.paperIds.length === 1 ? '' : 's'} stay in your library.`
            : 'It has no publications.'}</span>
          <button type="button" className="library-confirm-delete" onClick={() => deleteCollection(pendingDelete.id)}>Delete</button>
          <button type="button" className="library-confirm-cancel" onClick={() => setPendingDeleteId(null)}>Cancel</button>
        </div>}
        <div className="library-paper-list">{visiblePapers.length ? visiblePapers.map((paper) => <article key={paper.id}><button type="button" className="library-paper-open" onClick={(event) => openPaperDetails(paper, event.currentTarget)} aria-label={`Open details for ${paper.title || 'this publication'}`}><span>{paper.publishedYear || 'Year unavailable'}</span><h3>{paper.title || 'Untitled publication'}</h3><p>{paper.authorName}</p></button><div className="library-paper-actions"><select aria-label={`Collection for ${paper.title || 'this publication'}`} value={collectionOfPaper(paper.id)?.id || ''} onChange={(e) => assignPaper(paper.id, e.target.value)}><option value="">No collection</option>{library.collections.map((collection) => <option key={collection.id} value={collection.id}>{collection.name}</option>)}</select><button type="button" className="library-author-delete" onClick={() => handleRemovePaper(paper.id)} aria-label={`Remove ${paper.title || 'this publication'} from saved publications`} title="Remove saved publication"><i className="bx bx-trash" /></button></div></article>) : <p className="library-empty">{library.savedPapers.length ? 'No publications are assigned to this collection yet.' : 'Bookmark publications to organize them here.'}</p>}</div>
      </section>
    </main>

    {openPaper && <PublicationDetailsDialog
      paper={openPaper.paper}
      collectionName={collectionOfPaper(openPaper.paper.id)?.name || openPaper.collectionName}
      saved={library.savedPapers.some((paper) => paper.id === openPaper.paper.id)}
      onToggleSave={toggleOpenPaperSaved}
      onSelectAuthor={(author) => { setOpenPaper(null); onOpenAuthor({ id: author.id, name: author.name }); }}
      onClose={closePaperDetails}
    />}

    <footer className="dashboard-footer">
      <div className="footer-content">
        <div className="footer-section">
          <div className="footer-title">
            <img src="/assets/nmindex-icon.png" alt="" aria-hidden="true" className="footer-logo" />
            <h3>NmIndex</h3>
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
  </div>;
}
