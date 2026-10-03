import React, { useEffect, useRef, useState } from 'react';
import { onAuthStateChanged } from 'firebase/auth';
import { auth } from './firebase';
import {
  FEEDBACK_TYPES,
  ISSUE_CATEGORIES,
  LIMITS,
  submitFeedback,
  submitIssue,
  supportErrorMessage,
} from './services/supportService';
import './SupportDialogs.css';

const CONFIG = {
  feedback: {
    title: 'Send Feedback',
    eyebrow: 'WE ARE LISTENING',
    icon: 'bx-message-square-dots',
    submitLabel: 'Send Feedback',
    success: 'Thank you for your feedback.',
  },
  issue: {
    title: 'Report an Issue',
    eyebrow: 'SOMETHING WRONG?',
    icon: 'bx-bug',
    submitLabel: 'Submit Issue',
    success: 'Your issue has been reported successfully.',
  },
};

const emptyForm = { feedbackType: FEEDBACK_TYPES[0], message: '', title: '', category: ISSUE_CATEGORIES[0], description: '' };

const validate = (kind, form) => {
  const errors = {};
  const len = (v) => v.trim().length;
  if (kind === 'feedback') {
    if (len(form.message) < LIMITS.messageMin) errors.message = `Please write at least ${LIMITS.messageMin} characters.`;
    else if (len(form.message) > LIMITS.messageMax) errors.message = `Please keep it under ${LIMITS.messageMax} characters.`;
  } else {
    if (len(form.title) < LIMITS.titleMin) errors.title = `Please give the issue a title (at least ${LIMITS.titleMin} characters).`;
    else if (len(form.title) > LIMITS.titleMax) errors.title = `Please keep the title under ${LIMITS.titleMax} characters.`;
    if (len(form.description) < LIMITS.messageMin) errors.description = `Please describe the issue (at least ${LIMITS.messageMin} characters).`;
    else if (len(form.description) > LIMITS.messageMax) errors.description = `Please keep it under ${LIMITS.messageMax} characters.`;
  }
  return errors;
};

// Renders the Send Feedback / Report an Issue modal (kind = 'feedback' | 'issue')
// and the success toast. Mounted once in App.js and opened via useAppShell().
const SupportDialogs = ({ kind, onClose, onRequireLogin }) => {
  const [firebaseUser, setFirebaseUser] = useState(() => auth?.currentUser || null);
  const [form, setForm] = useState(emptyForm);
  const [errors, setErrors] = useState({});
  const [submitError, setSubmitError] = useState('');
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState('');
  const savingRef = useRef(false); // blocks double submits even before re-render
  const firstFieldRef = useRef(null);

  useEffect(() => (auth ? onAuthStateChanged(auth, setFirebaseUser) : undefined), []);

  // Fresh form each time a dialog opens.
  useEffect(() => {
    if (!kind) return;
    setForm(emptyForm);
    setErrors({});
    setSubmitError('');
    setTimeout(() => firstFieldRef.current?.focus(), 0);
  }, [kind]);

  useEffect(() => {
    if (!toast) return undefined;
    const id = setTimeout(() => setToast(''), 4000);
    return () => clearTimeout(id);
  }, [toast]);

  const close = () => {
    if (!savingRef.current) onClose();
  };

  useEffect(() => {
    if (!kind) return undefined;
    const onKey = (e) => { if (e.key === 'Escape') close(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  const set = (field) => (e) => {
    setForm((prev) => ({ ...prev, [field]: e.target.value }));
    if (errors[field]) setErrors((prev) => ({ ...prev, [field]: undefined }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (savingRef.current) return;
    const found = validate(kind, form);
    setErrors(found);
    setSubmitError('');
    if (Object.keys(found).length) return;

    savingRef.current = true;
    setSaving(true);
    try {
      if (kind === 'feedback') await submitFeedback(form);
      else await submitIssue(form);
      savingRef.current = false;
      setToast(CONFIG[kind].success);
      onClose();
    } catch (err) {
      setSubmitError(supportErrorMessage(err, 'Something went wrong while sending. Please try again.'));
    } finally {
      savingRef.current = false;
      setSaving(false);
    }
  };

  const cfg = kind ? CONFIG[kind] : null;

  return (
    <>
      {toast && <div className="support-toast" role="status"><i className="bx bx-check-circle" aria-hidden="true" /> {toast}</div>}

      {cfg && (
        <div className="support-modal" role="presentation" onMouseDown={(e) => { if (e.target === e.currentTarget) close(); }}>
          <div className="support-dialog" role="dialog" aria-modal="true" aria-labelledby="support-dialog-title">
            <div className="support-dialog-header">
              <span aria-hidden="true"><i className={`bx ${cfg.icon}`} /></span>
              <div>
                <small>{cfg.eyebrow}</small>
                <h2 id="support-dialog-title">{cfg.title}</h2>
              </div>
              <button type="button" onClick={close} aria-label="Close" disabled={saving}><i className="bx bx-x" aria-hidden="true" /></button>
            </div>

            {!firebaseUser ? (
              <div className="support-login-required">
                <p>Please log in to {kind === 'feedback' ? 'send feedback' : 'report an issue'}. We only accept submissions from signed-in users.</p>
                <div className="support-actions">
                  <button type="button" onClick={close}>Cancel</button>
                  <button type="button" className="primary" onClick={onRequireLogin}>Go to Login</button>
                </div>
              </div>
            ) : (
              <form onSubmit={handleSubmit} noValidate>
                <p className="support-signed-in">Signed in as <strong>{firebaseUser.email}</strong></p>

                {kind === 'feedback' ? (
                  <>
                    <label className="support-field">
                      Feedback Type
                      <select ref={firstFieldRef} value={form.feedbackType} onChange={set('feedbackType')} disabled={saving}>
                        {FEEDBACK_TYPES.map((t) => <option key={t}>{t}</option>)}
                      </select>
                    </label>
                    <label className="support-field">
                      Your Feedback
                      <textarea
                        rows={6}
                        value={form.message}
                        onChange={set('message')}
                        disabled={saving}
                        maxLength={LIMITS.messageMax}
                        placeholder="Tell us what you think, or what would make ScholarMetrics better…"
                        aria-invalid={Boolean(errors.message)}
                      />
                      {errors.message && <span className="support-error">{errors.message}</span>}
                    </label>
                  </>
                ) : (
                  <>
                    <label className="support-field">
                      Issue Title
                      <input
                        ref={firstFieldRef}
                        value={form.title}
                        onChange={set('title')}
                        disabled={saving}
                        maxLength={LIMITS.titleMax}
                        placeholder="e.g. Dashboard does not load"
                        aria-invalid={Boolean(errors.title)}
                      />
                      {errors.title && <span className="support-error">{errors.title}</span>}
                    </label>
                    <label className="support-field">
                      Category
                      <select value={form.category} onChange={set('category')} disabled={saving}>
                        {ISSUE_CATEGORIES.map((c) => <option key={c}>{c}</option>)}
                      </select>
                    </label>
                    <label className="support-field">
                      Description
                      <textarea
                        rows={6}
                        value={form.description}
                        onChange={set('description')}
                        disabled={saving}
                        maxLength={LIMITS.messageMax}
                        placeholder="What happened? What did you expect? Steps to reproduce help a lot."
                        aria-invalid={Boolean(errors.description)}
                      />
                      {errors.description && <span className="support-error">{errors.description}</span>}
                    </label>
                  </>
                )}

                {submitError && <p className="support-submit-error" role="alert">{submitError}</p>}

                <div className="support-actions">
                  <button type="button" onClick={close} disabled={saving}>Cancel</button>
                  <button type="submit" className="primary" disabled={saving}>
                    {saving ? <><i className="bx bx-loader-alt bx-spin" aria-hidden="true" /> Sending…</> : cfg.submitLabel}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </>
  );
};

export default SupportDialogs;
