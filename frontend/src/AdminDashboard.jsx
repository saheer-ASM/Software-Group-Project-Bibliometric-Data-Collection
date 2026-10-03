import React, { useEffect, useMemo, useState } from 'react';
import AppNavbar from './AppNavbar';
import {
  FEEDBACK_STATUSES,
  ISSUE_STATUSES,
  LIMITS,
  deleteSubmission,
  supportErrorMessage,
  updateSubmission,
  watchSubmissions,
} from './services/supportService';
import { FooterQuickLinks, FooterContactLinks, FooterCopyright } from './FooterParts';
import './Dashboard.css';
import './SupportDialogs.css';
import './AdminDashboard.css';

// Admin area: all feedback and issue reports. Only reachable when the user's
// token has the `admin` custom claim; Firestore Security Rules enforce the same
// claim, so a non-admin opening this page would just get "permission denied".

const TABS = {
  feedback: {
    label: 'Feedback',
    icon: 'bx-message-square-dots',
    statuses: FEEDBACK_STATUSES,
    summary: (d) => d.feedbackType,
    body: (d) => d.message,
  },
  issues: {
    label: 'Issues',
    icon: 'bx-bug',
    statuses: ISSUE_STATUSES,
    summary: (d) => d.title,
    body: (d) => d.description,
  },
};

const formatDate = (ts, withTime = false) => {
  const date = ts?.toDate?.();
  if (!date) return '—';
  return date.toLocaleString('en-GB', withTime
    ? { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }
    : { day: '2-digit', month: 'short', year: 'numeric' });
};

const statusClass = (status) => `admin-status admin-status-${status.toLowerCase().replace(/\s+/g, '-')}`;

const AdminDashboard = ({ onBack, onNavigateToExplorer, onNavigateToLibrary, onNavigateToAbout, onNavigateToProfile, onLogout }) => {
  const [tab, setTab] = useState('feedback');
  const [data, setData] = useState({ feedback: null, issues: null });
  const [errors, setErrors] = useState({ feedback: '', issues: '' });
  const [statusFilter, setStatusFilter] = useState('All');
  const [selected, setSelected] = useState(null); // { collection, item }

  useEffect(() => {
    const subscribe = (name) => watchSubmissions(
      name,
      (items) => {
        setData((prev) => ({ ...prev, [name]: items }));
        setErrors((prev) => ({ ...prev, [name]: '' }));
      },
      (err) => setErrors((prev) => ({ ...prev, [name]: supportErrorMessage(err, 'Could not load submissions.') })),
    );
    const unsubs = [subscribe('feedback'), subscribe('issues')];
    return () => unsubs.forEach((u) => u());
  }, []);

  const cfg = TABS[tab];
  const items = data[tab];
  const visible = useMemo(
    () => (items || []).filter((d) => statusFilter === 'All' || d.status === statusFilter),
    [items, statusFilter],
  );

  const openCount = (name) => (data[name] || [])
    .filter((d) => d.status === (name === 'feedback' ? 'New' : 'Open')).length;

  // Keep the open dialog in sync with live updates (or close it if deleted).
  const selectedItem = selected && (data[selected.collection] || []).find((d) => d.id === selected.id);

  return (
    <div className="dashboard-container">
      <AppNavbar activePage="admin" onDashboard={onBack} onExplorer={onNavigateToExplorer} onLibrary={onNavigateToLibrary} onAbout={onNavigateToAbout} onProfile={onNavigateToProfile} onLogout={onLogout} />

      <main className="dashboard-main admin-main">
        <div className="admin-heading">
          <h2>Admin Dashboard</h2>
          <p>Feedback and issue reports from ScholarMetrics users.</p>
        </div>

        <div className="admin-tabs" role="tablist">
          {Object.entries(TABS).map(([key, t]) => (
            <button
              key={key}
              type="button"
              role="tab"
              aria-selected={tab === key}
              className={`admin-tab${tab === key ? ' active' : ''}`}
              onClick={() => { setTab(key); setStatusFilter('All'); }}
            >
              <i className={`bx ${t.icon}`} aria-hidden="true" /> {t.label}
              {openCount(key) > 0 && <span className="admin-tab-badge">{openCount(key)}</span>}
            </button>
          ))}
        </div>

        <section className="admin-panel">
          <div className="admin-panel-header">
            <h3>{cfg.label} <span>({items ? items.length : '…'})</span></h3>
            <label>
              Status
              <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
                <option>All</option>
                {cfg.statuses.map((s) => <option key={s}>{s}</option>)}
              </select>
            </label>
          </div>

          {errors[tab] && <p className="admin-error" role="alert">{errors[tab]}</p>}
          {!errors[tab] && items === null && <p className="admin-empty" role="status">Loading…</p>}
          {!errors[tab] && items && visible.length === 0 && (
            <p className="admin-empty">No {cfg.label.toLowerCase()} {statusFilter !== 'All' ? `with status "${statusFilter}"` : 'yet'}.</p>
          )}

          {visible.length > 0 && (
            <div className="admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>{tab === 'feedback' ? 'Type' : 'Title'}</th>
                    {tab === 'issues' && <th>Category</th>}
                    <th>User</th>
                    <th>Date</th>
                    <th>Status</th>
                    <th aria-label="Actions" />
                  </tr>
                </thead>
                <tbody>
                  {visible.map((d) => (
                    <tr key={d.id}>
                      <td className="admin-cell-main">{cfg.summary(d)}</td>
                      {tab === 'issues' && <td>{d.category}</td>}
                      <td className="admin-cell-user">{d.userEmail}</td>
                      <td>{formatDate(d.createdAt)}</td>
                      <td><span className={statusClass(d.status)}>{d.status}</span></td>
                      <td>
                        <button type="button" className="admin-view-btn" onClick={() => setSelected({ collection: tab, id: d.id })}>
                          View
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </main>

      {selectedItem && (
        <SubmissionDialog
          collectionName={selected.collection}
          item={selectedItem}
          onClose={() => setSelected(null)}
        />
      )}

      <footer className="dashboard-footer">
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

const SubmissionDialog = ({ collectionName, item, onClose }) => {
  const cfg = TABS[collectionName];
  const [status, setStatus] = useState(item.status);
  const [response, setResponse] = useState(item.adminResponse || '');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState({ type: '', text: '' });
  const dirty = status !== item.status || response.trim() !== (item.adminResponse || '');

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape' && !busy) onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [busy, onClose]);

  const save = async () => {
    setBusy(true);
    setMessage({ type: '', text: '' });
    try {
      await updateSubmission(collectionName, item.id, { status, adminResponse: response });
      setMessage({ type: 'success', text: 'Saved.' });
    } catch (err) {
      setMessage({ type: 'error', text: supportErrorMessage(err, 'Could not save the changes.') });
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    if (!window.confirm('Delete this submission permanently? This cannot be undone.')) return;
    setBusy(true);
    try {
      await deleteSubmission(collectionName, item.id);
      onClose();
    } catch (err) {
      setMessage({ type: 'error', text: supportErrorMessage(err, 'Could not delete the submission.') });
      setBusy(false);
    }
  };

  return (
    <div className="support-modal" role="presentation" onMouseDown={(e) => { if (e.target === e.currentTarget && !busy) onClose(); }}>
      <div className="support-dialog admin-dialog" role="dialog" aria-modal="true" aria-labelledby="admin-dialog-title">
        <div className="support-dialog-header">
          <span aria-hidden="true"><i className={`bx ${cfg.icon}`} /></span>
          <div>
            <small>{collectionName === 'feedback' ? 'FEEDBACK' : `ISSUE · ${item.category.toUpperCase()}`}</small>
            <h2 id="admin-dialog-title">{cfg.summary(item)}</h2>
          </div>
          <button type="button" onClick={onClose} aria-label="Close" disabled={busy}><i className="bx bx-x" aria-hidden="true" /></button>
        </div>

        <dl className="admin-meta">
          <div><dt>From</dt><dd>{item.userEmail}</dd></div>
          <div><dt>Submitted</dt><dd>{formatDate(item.createdAt, true)}</dd></div>
          <div><dt>Last updated</dt><dd>{formatDate(item.updatedAt, true)}</dd></div>
          <div><dt>User ID</dt><dd className="admin-mono">{item.userId}</dd></div>
        </dl>

        <div className="admin-body">{cfg.body(item)}</div>

        <label className="support-field">
          Status
          <select value={status} onChange={(e) => setStatus(e.target.value)} disabled={busy}>
            {cfg.statuses.map((s) => <option key={s}>{s}</option>)}
          </select>
        </label>
        <label className="support-field">
          Admin response (optional, internal note)
          <textarea rows={3} value={response} maxLength={LIMITS.adminResponseMax} onChange={(e) => setResponse(e.target.value)} disabled={busy} />
        </label>

        {message.text && (
          <p className={message.type === 'error' ? 'support-submit-error' : 'admin-saved'} role={message.type === 'error' ? 'alert' : 'status'}>
            {message.text}
          </p>
        )}

        <div className="support-actions admin-dialog-actions">
          <button type="button" className="admin-delete-btn" onClick={remove} disabled={busy}>
            <i className="bx bx-trash" aria-hidden="true" /> Delete
          </button>
          <span className="admin-actions-spacer" />
          <button type="button" onClick={onClose} disabled={busy}>Close</button>
          <button type="button" className="primary" onClick={save} disabled={busy || !dirty}>
            {busy ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default AdminDashboard;
