import React, { useEffect, useRef, useState } from 'react';
import { API_BASE_URL } from '../../config/api';

export default function AuthorSelector({ selectedAuthors, onChange, onCompare, loading }) {
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState([]);
  const [searching, setSearching] = useState(false);
  const controllerRef = useRef(null);

  useEffect(() => {
    const value = query.trim();
    if (value.length < 2) {
      setSuggestions([]);
      return undefined;
    }
    const timer = setTimeout(async () => {
      controllerRef.current?.abort();
      const controller = new AbortController();
      controllerRef.current = controller;
      setSearching(true);
      try {
        const response = await fetch(`${API_BASE_URL}/api/authors?q=${encodeURIComponent(value)}`, { signal: controller.signal });
        if (!response.ok) throw new Error('Author search failed');
        const authors = await response.json();
        setSuggestions(authors.filter((author) => !selectedAuthors.some((item) => item.id === author.id)));
      } catch (error) {
        if (error.name !== 'AbortError') setSuggestions([]);
      } finally {
        if (controllerRef.current === controller) setSearching(false);
      }
    }, 250);
    return () => clearTimeout(timer);
  }, [query, selectedAuthors]);

  const addAuthor = (author) => {
    if (selectedAuthors.length >= 3 || selectedAuthors.some((item) => item.id === author.id)) return;
    onChange([...selectedAuthors, author]);
    setQuery('');
    setSuggestions([]);
  };

  return <section className="ac-panel ac-selector" aria-labelledby="selected-authors-title">
    <div className="ac-section-heading">
      <div><h2 id="selected-authors-title">Selected authors</h2><p>Choose two or three researchers to compare.</p></div>
      <span>{selectedAuthors.length}/3 selected</span>
    </div>
    <div className="ac-search-wrap">
      <i className="bx bx-search" aria-hidden="true"></i>
      <input
        type="search"
        value={query}
        placeholder={selectedAuthors.length >= 3 ? 'Maximum of three authors selected' : 'Search by author name'}
        disabled={selectedAuthors.length >= 3}
        onChange={(event) => setQuery(event.target.value)}
        aria-label="Search authors to compare"
      />
      {query.trim().length >= 2 && <div className="ac-suggestions">
        {searching ? <p>Searching authors…</p> : suggestions.length ? suggestions.map((author) =>
          <button type="button" key={author.id} onClick={() => addAuthor(author)}>
            <i className="bx bxs-user-circle"></i><span><strong>{author.name}</strong><small>{author.id}</small></span>
          </button>
        ) : <p>No matching authors available.</p>}
      </div>}
    </div>
    <div className="ac-selected-list">
      {selectedAuthors.map((author, index) => <article key={author.id} className="ac-selected-author">
        <span className={`ac-author-dot ac-color-${index}`}></span>
        <div><strong>{author.name}</strong><small>{author.id}</small></div>
        <button type="button" onClick={() => onChange(selectedAuthors.filter((item) => item.id !== author.id))} aria-label={`Remove ${author.name}`}>
          <i className="bx bx-x"></i>
        </button>
      </article>)}
    </div>
    <button className="ac-compare-button" type="button" disabled={selectedAuthors.length < 2 || loading} onClick={onCompare}>
      <i className="bx bx-bar-chart-alt-2"></i>{loading ? 'Comparing…' : 'Compare authors'}
    </button>
  </section>;
}
