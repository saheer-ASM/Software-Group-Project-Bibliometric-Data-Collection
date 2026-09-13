import React, { useEffect, useState } from 'react';
import { getLibrary, saveLibrary } from './services/researchLibrary';
import './Dashboard.css';
import './Library.css';
import AppNavbar from './AppNavbar';

export default function Library({ user, onBack, onOpenAuthor, onNavigateToAbout, onNavigateToProfile, onLogout, hasSearchedAuthor }) {
  const userId = user?.id || user?.email;
  const [library, setLibrary] = useState(() => getLibrary(userId));
  const [collectionName, setCollectionName] = useState('');
  const [activeCollection, setActiveCollection] = useState('all');

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
  const removeSavedAuthor = (authorId) => persist({ ...library, savedAuthors: library.savedAuthors.filter((author) => author.id !== authorId) });
  const removeRecentAuthor = (authorId) => persist({ ...library, recentAuthors: library.recentAuthors.filter((author) => author.id !== authorId) });
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
      <div className="library-grid">
        <section className="library-panel"><h2><i className="bx bxs-user-pin" /> Saved authors <small>{library.savedAuthors.length}</small></h2>
          <div className="library-items">{library.savedAuthors.length ? library.savedAuthors.map((author) => <div className="library-author-row" key={author.id}><button className="library-author-open" onClick={() => onOpenAuthor(author.name)}><i className="bx bxs-user-circle" /><span><strong>{author.name}</strong><small>{author.id}</small></span><i className="bx bx-chevron-right" /></button><button className="library-author-delete" onClick={() => removeSavedAuthor(author.id)} aria-label={`Remove ${author.name} from saved authors`} title="Remove saved author"><i className="bx bx-trash" /></button></div>) : <p className="library-empty">Save an author from their Data Explorer profile.</p>}</div>
        </section>
        <section className="library-panel"><h2><i className="bx bx-history" /> Recently viewed <small>{library.recentAuthors.length}</small></h2>
          <div className="library-items">{library.recentAuthors.length ? library.recentAuthors.map((author) => <div className="library-author-row" key={author.id}><button className="library-author-open" onClick={() => onOpenAuthor(author.name)}><i className="bx bx-time-five" /><span><strong>{author.name}</strong><small>{new Date(author.viewedAt).toLocaleDateString()}</small></span><i className="bx bx-chevron-right" /></button><button className="library-author-delete" onClick={() => removeRecentAuthor(author.id)} aria-label={`Remove ${author.name} from recently viewed`} title="Remove recent author"><i className="bx bx-trash" /></button></div>) : <p className="library-empty">Viewed researchers will appear here.</p>}</div>
        </section>
      </div>
      <section className="library-panel library-papers"><div className="library-panel-title"><h2><i className="bx bx-file" /> Saved publications <small>{library.savedPapers.length}</small></h2><form onSubmit={createCollection}><input value={collectionName} onChange={(e) => setCollectionName(e.target.value)} placeholder="New collection name" /><button>Create collection</button></form></div>
        <div className="library-collections" role="group" aria-label="Filter publications by collection">
          <button className={activeCollection === 'all' ? 'active' : ''} onClick={() => setActiveCollection('all')}>All <strong>{library.savedPapers.length}</strong></button>
          {library.collections.map((collection) => <button key={collection.id} className={activeCollection === collection.id ? 'active' : ''} onClick={() => setActiveCollection(collection.id)}>{collection.name} <strong>{collection.paperIds.length}</strong></button>)}
        </div>
        <div className="library-paper-list">{visiblePapers.length ? visiblePapers.map((paper) => <article key={paper.id}><div><span>{paper.publishedYear || 'Year unavailable'}</span><h3>{paper.title}</h3><p>{paper.authorName}</p></div><select value={library.collections.find((item) => item.paperIds.includes(paper.id))?.id || ''} onChange={(e) => assignPaper(paper.id, e.target.value)}><option value="">No collection</option>{library.collections.map((collection) => <option key={collection.id} value={collection.id}>{collection.name}</option>)}</select></article>) : <p className="library-empty">{library.savedPapers.length ? 'No publications are assigned to this collection yet.' : 'Bookmark publications to organize them here.'}</p>}</div>
      </section>
    </main>
  </div>;
}
