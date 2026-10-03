import React, { useCallback, useEffect, useRef, useState } from 'react';
import { onAuthStateChanged, signOut } from 'firebase/auth';
import { auth, missingConfig, refreshEmailVerified, sendVerificationEmail } from './firebase';
import { authErrorMessage } from './authErrors';
import './AuthForm.css';
import './VerifyEmail.css';

const POLL_INTERVAL_MS = 5000;
const RESEND_COOLDOWN_S = 60;

const firebaseErrorMessage = (err, fallback) => authErrorMessage(err, err?.message || fallback);

// state shape passed by AuthForm via navigation:
//   { notice?: string, error?: string }
const VerifyEmail = ({ onNavigate, initialNotice = '', initialError = '' }) => {
  const [status, setStatus] = useState('initializing'); // initializing | no-session | pending | verified
  const [email, setEmail] = useState('');
  const [checking, setChecking] = useState(false);
  const [resending, setResending] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  const [notice, setNotice] = useState(initialNotice);
  const [error, setError] = useState(initialError);
  const userRef = useRef(null);

  const completeVerification = useCallback(async () => {
    setStatus('verified');
    // The user logs in normally afterwards, so drop the registration session.
    await signOut(auth).catch(() => {});
    setTimeout(() => {
      onNavigate('/login', { notice: 'Your email has been verified. You can now log in.' });
    }, 1500);
  }, [onNavigate]);

  const checkVerification = useCallback(async ({ silent = false } = {}) => {
    const user = userRef.current;
    if (!user) return;
    if (!silent) {
      setChecking(true);
      setError('');
      setNotice('');
    }
    try {
      const verified = await refreshEmailVerified(user);
      if (verified) {
        await completeVerification();
      } else if (!silent) {
        setNotice('Your email is not verified yet. Open the link in the email, then check again.');
      }
    } catch (err) {
      if (!silent) setError(firebaseErrorMessage(err, 'Could not check verification status.'));
      if (err?.code === 'auth/user-token-expired' || err?.code === 'auth/user-not-found') {
        setStatus('no-session');
      }
    } finally {
      if (!silent) setChecking(false);
    }
  }, [completeVerification]);

  // Wait for Firebase to restore its session (it survives page reloads).
  useEffect(() => {
    if (missingConfig.length > 0 || !auth) {
      setStatus('no-session');
      setError('Firebase web config is missing. Fill frontend/.env from Firebase Project settings.');
      return undefined;
    }
    const unsubscribe = onAuthStateChanged(auth, (user) => {
      userRef.current = user;
      if (!user) {
        setStatus('no-session');
        return;
      }
      setEmail(user.email || '');
      if (user.emailVerified) {
        completeVerification();
      } else {
        setStatus('pending');
      }
    });
    return unsubscribe;
  }, [completeVerification]);

  // Periodically re-check while the page is visible.
  useEffect(() => {
    if (status !== 'pending') return undefined;
    const id = setInterval(() => {
      if (document.visibilityState === 'visible') checkVerification({ silent: true });
    }, POLL_INTERVAL_MS);
    const onFocus = () => checkVerification({ silent: true });
    window.addEventListener('focus', onFocus);
    return () => {
      clearInterval(id);
      window.removeEventListener('focus', onFocus);
    };
  }, [status, checkVerification]);

  useEffect(() => {
    if (cooldown <= 0) return undefined;
    const id = setTimeout(() => setCooldown((s) => s - 1), 1000);
    return () => clearTimeout(id);
  }, [cooldown]);

  const handleResend = async () => {
    const user = userRef.current;
    if (!user || cooldown > 0) return;
    setResending(true);
    setError('');
    setNotice('');
    try {
      await sendVerificationEmail(user);
      setNotice(`A new verification email has been sent to ${user.email}.`);
      setCooldown(RESEND_COOLDOWN_S);
    } catch (err) {
      setError(firebaseErrorMessage(err, 'Could not resend the verification email.'));
    } finally {
      setResending(false);
    }
  };

  const handleUseDifferentAccount = async () => {
    await signOut(auth).catch(() => {});
    onNavigate('/register');
  };

  return (
    <div className="verify-page">
      <div className="verify-card" role="main">
        <div className="verify-icon" aria-hidden="true">
          <i className={`bx ${status === 'verified' ? 'bx-check-circle' : 'bx-envelope'}`} />
        </div>

        {status === 'initializing' && (
          <>
            <h1>Please verify your email address</h1>
            <p className="verify-text" role="status">Loading your registration…</p>
          </>
        )}

        {status === 'no-session' && (
          <>
            <h1>No pending verification</h1>
            <p className="verify-text">
              We couldn't find a registration waiting for email verification in this browser.
              If you already registered, log in and you'll be brought back here if your email still needs verifying.
            </p>
            {error && <p className="verify-message error" role="alert">{error}</p>}
            <div className="verify-actions">
              <button type="button" className="btn" onClick={() => onNavigate('/login')}>Go to Login</button>
              <button type="button" className="btn btn-secondary" onClick={() => onNavigate('/register')}>Register</button>
            </div>
          </>
        )}

        {status === 'pending' && (
          <>
            <h1>Please verify your email address</h1>
            <p className="verify-text">We sent a verification link to</p>
            <p className="verify-email">{email}</p>
            <p className="verify-text">
              Please check your inbox (and your spam folder) and click the link to activate your account.
              This page updates automatically once your email is verified.
            </p>

            {notice && <p className="verify-message info" role="status">{notice}</p>}
            {error && <p className="verify-message error" role="alert">{error}</p>}

            <div className="verify-actions">
              <button
                type="button"
                className="btn"
                onClick={() => checkVerification()}
                disabled={checking}
              >
                {checking ? (
                  <><i className="bx bx-loader-alt bx-spin" aria-hidden="true" /> Checking…</>
                ) : (
                  <><i className="bx bx-refresh" aria-hidden="true" /> Refresh / Check Verification</>
                )}
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={handleResend}
                disabled={resending || cooldown > 0}
              >
                {resending
                  ? 'Sending…'
                  : cooldown > 0
                    ? `Resend Verification Email (${cooldown}s)`
                    : 'Resend Verification Email'}
              </button>
            </div>

            <button type="button" className="verify-link" onClick={handleUseDifferentAccount}>
              Wrong email? Register with a different address
            </button>
          </>
        )}

        {status === 'verified' && (
          <>
            <h1>Email verified!</h1>
            <p className="verify-text" role="status">Redirecting you to the login page…</p>
          </>
        )}
      </div>
    </div>
  );
};

export default VerifyEmail;
