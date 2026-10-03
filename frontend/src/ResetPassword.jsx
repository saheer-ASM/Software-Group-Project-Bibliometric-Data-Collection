import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { auth } from './firebase';
import { API_BASE_URL } from './config/api';
import { checkPassword } from './authValidation';
import { authErrorMessage } from './authErrors';
import './AuthForm.css';
import './VerifyEmail.css';

// Handles the links in Firebase's emails once the project's action URL points
// here (Firebase Console > Authentication > Templates > Customize action URL).
// That setting applies to every Firebase email, so besides password resets
// (mode=resetPassword) this also completes email-verification links
// (mode=verifyEmail).

// Action codes are single-use. Remember each check per code so a repeated
// effect run (React StrictMode in development, or a re-mount) reuses the first
// result instead of spending the code twice and reporting it as "already used".
const actionChecks = new Map();
const checkActionCode = (mode, oobCode) => {
  const key = `${mode}:${oobCode}`;
  if (!actionChecks.has(key)) {
    actionChecks.set(key, (async () => {
      if (mode === 'verifyEmail') {
        const { applyActionCode } = await import('firebase/auth');
        await applyActionCode(auth, oobCode);
        return { status: 'email-verified' };
      }
      const { verifyPasswordResetCode } = await import('firebase/auth');
      return { status: 'ready', email: await verifyPasswordResetCode(auth, oobCode) };
    })());
  }
  return actionChecks.get(key);
};

const ResetPassword = ({ onLogin, onNavigate }) => {
  const params = new URLSearchParams(window.location.search);
  const mode = params.get('mode') || 'resetPassword';
  const oobCode = params.get('oobCode') || '';

  const [email, setEmail] = useState('');
  // verifying | ready | invalid | done | email-verified
  const [status, setStatus] = useState('verifying');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showNew, setShowNew] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { rules, strong } = checkPassword(newPassword);

  useEffect(() => {
    if (!oobCode || !auth) {
      setStatus('invalid');
      return;
    }
    checkActionCode(mode, oobCode)
      .then((result) => {
        if (result.email) setEmail(result.email);
        setStatus(result.status);
      })
      .catch(() => setStatus('invalid'));
  }, [mode, oobCode]);

  const navigate = useNavigate();
  const goToSignIn = () => (onNavigate || navigate)('/login');

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (loading) return;
    setError('');
    if (!newPassword || !confirmPassword) {
      setError('Please fill in both password fields.');
      return;
    }
    if (!strong) {
      setError('Your new password does not meet all the requirements.');
      return;
    }
    if (newPassword !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    setLoading(true);
    try {
      const { confirmPasswordReset } = await import('firebase/auth');
      await confirmPasswordReset(auth, oobCode, newPassword);
    } catch (err) {
      setError(authErrorMessage(err, 'Could not reset your password. The link may have expired; request a new one.'));
      setLoading(false);
      return;
    }

    // The password is changed. Signing in straight away is a convenience; if it
    // does not work, the user simply signs in with the new password.
    try {
      const { signInWithEmailAndPassword } = await import('firebase/auth');
      const result = await signInWithEmailAndPassword(auth, email, newPassword);
      const idToken = await result.user.getIdToken();
      const res = await fetch(`${API_BASE_URL}/api/auth/reset-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ idToken }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.message);
      // Unfinished Google registration: no session yet. The next sign-in
      // continues on Complete Your Profile.
      if (data.profileCompleted === false || !data.token) throw new Error('profile incomplete');
      localStorage.setItem('token', data.token);
      onLogin(data.user); // App navigates to the dashboard
    } catch {
      setStatus('done');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="verify-page">
      <div className="verify-card reset-card" role="main">
        {status === 'verifying' && (
          <>
            <div className="verify-icon" aria-hidden="true"><i className="bx bx-lock-alt" /></div>
            <h1>{mode === 'verifyEmail' ? 'Verifying your email' : 'Reset Password'}</h1>
            <p className="verify-text" role="status">Checking your link…</p>
          </>
        )}

        {status === 'invalid' && (
          <>
            <div className="verify-icon reset-icon-error" aria-hidden="true"><i className="bx bx-error-circle" /></div>
            <h1>Link expired or invalid</h1>
            <p className="verify-text">
              This link is invalid, has expired, or has already been used.
              {mode === 'verifyEmail' ? ' Log in to request a new verification email.' : ' Request a new one from "Forgot Password?" on the sign-in page.'}
            </p>
            <div className="verify-actions">
              <button type="button" className="btn" onClick={goToSignIn}>Back to Sign In</button>
            </div>
          </>
        )}

        {status === 'email-verified' && (
          <>
            <div className="verify-icon reset-icon-success" aria-hidden="true"><i className="bx bx-check" /></div>
            <h1>Email verified!</h1>
            <p className="verify-text">Your email address has been verified. You can now sign in.</p>
            <div className="verify-actions">
              <button type="button" className="btn" onClick={goToSignIn}>Back to Sign In</button>
            </div>
          </>
        )}

        {status === 'done' && (
          <>
            <div className="verify-icon reset-icon-success" aria-hidden="true"><i className="bx bx-check" /></div>
            <h1>Password updated</h1>
            <p className="verify-text">Your password has been changed. Sign in with your new password.</p>
            <div className="verify-actions">
              <button type="button" className="btn" onClick={goToSignIn}>Back to Sign In</button>
            </div>
          </>
        )}

        {status === 'ready' && (
          <form onSubmit={handleSubmit} noValidate>
            <div className="verify-icon" aria-hidden="true"><i className="bx bx-lock-alt" /></div>
            <h1>Reset Password</h1>
            <p className="verify-text">Set a new password for</p>
            <p className="verify-email">{email}</p>

            <div className="input-box">
              <input
                type={showNew ? 'text' : 'password'}
                className="has-toggle"
                placeholder="New Password"
                autoComplete="new-password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                disabled={loading}
                aria-describedby="reset-password-rules"
              />
              <button type="button" className="password-toggle" onClick={() => setShowNew((v) => !v)} aria-label={showNew ? 'Hide new password' : 'Show new password'}>
                <i className={`bx ${showNew ? 'bx-hide' : 'bx-show'}`} aria-hidden="true" />
              </button>
            </div>
            {newPassword && (
              <ul id="reset-password-rules" className="password-rules">
                {rules.map((rule) => (
                  <li key={rule.id} className={rule.met ? 'met' : ''}>
                    <i className={`bx ${rule.met ? 'bx-check-circle' : 'bx-circle'}`} aria-hidden="true" />
                    {rule.label}
                  </li>
                ))}
              </ul>
            )}
            <div className="input-box">
              <input
                type={showConfirm ? 'text' : 'password'}
                className="has-toggle"
                placeholder="Confirm New Password"
                autoComplete="new-password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                disabled={loading}
              />
              <button type="button" className="password-toggle" onClick={() => setShowConfirm((v) => !v)} aria-label={showConfirm ? 'Hide confirm password' : 'Show confirm password'}>
                <i className={`bx ${showConfirm ? 'bx-hide' : 'bx-show'}`} aria-hidden="true" />
              </button>
            </div>

            {error && <p className="verify-message error" role="alert">{error}</p>}

            <div className="verify-actions">
              <button type="submit" className="btn" disabled={loading}>
                {loading ? 'Resetting…' : 'Reset Password'}
              </button>
              <button type="button" className="btn btn-secondary" onClick={goToSignIn} disabled={loading}>
                Back to Sign In
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};

export default ResetPassword;
