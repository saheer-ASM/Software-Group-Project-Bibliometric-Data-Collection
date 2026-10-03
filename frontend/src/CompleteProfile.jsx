import React, { useCallback, useEffect, useRef, useState } from 'react';
import { onAuthStateChanged, reload, signOut, updateProfile } from 'firebase/auth';
import {
  auth,
  hasPasswordSignIn,
  linkPasswordCredential,
  refreshEmailVerified,
  sendVerificationEmail,
} from './firebase';
import { checkPassword } from './authValidation';
import { authErrorMessage } from './authErrors';
import {
  RESEND_COOLDOWN_S,
  completeRegistration,
  getRegistrationState,
  saveRegistrationProfile,
} from './services/registrationService';
import './AuthForm.css';
import './VerifyEmail.css';

// Google registration (route /complete-profile), resumable at any step:
//   1. Complete Your Profile  - full name + designation (saved on the server)
//   2. Set Your Password      - linked to the SAME Firebase user (linkWithCredential)
//   3. Check Your Email       - Firebase verification email; "I've Verified"
//                               reloads the Firebase user and checks emailVerified
//   -> /api/auth/complete-profile issues the session -> Dashboard.
// The backend reports which step is left, so a returning user resumes there.

const VERIFY_RETURN_PATH = '/complete-profile';

const errorMessage = (err) => {
  switch (err?.code) {
    case 'auth/credential-already-in-use':
    case 'auth/email-already-in-use':
      return 'An email/password sign-in already exists for this email on another account. Sign in with your email and password instead.';
    case 'auth/weak-password':
    case 'auth/password-does-not-meet-requirements':
      return 'That password does not meet the password requirements.';
    case 'auth/popup-closed-by-user':
    case 'auth/cancelled-popup-request':
      return 'Please confirm your Google account in the pop-up to finish setting your password.';
    case 'auth/too-many-requests':
      return 'Too many requests. Please wait a few minutes and try again.';
    case 'EMAIL_NOT_VERIFIED':
      return 'Your email has not been verified yet. Please check your inbox and Spam/Junk folder, then click the verification link.';
    default:
      return authErrorMessage(err, err?.message || 'Something went wrong. Please try again.');
  }
};

const STEP_NUMBER = { profile: 1, password: 2, verify: 3 };

const CompleteProfile = ({ onLogin, onNavigate, initialState }) => {
  // loading | no-session | profile | password | verify
  const [step, setStep] = useState('loading');
  const [firebaseUser, setFirebaseUser] = useState(null);
  const [fullName, setFullName] = useState('');
  const [designation, setDesignation] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [errors, setErrors] = useState({});
  const [message, setMessage] = useState({ type: '', text: '' });
  const [busy, setBusy] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  const busyRef = useRef(false);
  const started = useRef(false);
  const { rules, strong } = checkPassword(password);

  const finishWithSession = useCallback((data) => {
    localStorage.setItem('token', data.token);
    onLogin(data.user);
  }, [onLogin]);

  // Apply a registration state returned by the backend.
  const applyState = useCallback((data) => {
    if (data.status === 'COMPLETED' && data.token) {
      finishWithSession(data);
      return;
    }
    if (data.status === 'COMPLETED_UNVERIFIED') {
      onNavigate('/verify-email', { notice: 'Please verify your email address to finish signing in.' });
      return;
    }
    if (data.status === 'NOT_REGISTERED') {
      onNavigate('/register');
      return;
    }
    if (data.profile) {
      setFullName((prev) => prev || data.profile.username || '');
      setDesignation((prev) => prev || data.profile.designation || '');
    }
    setStep(data.step || 'profile');
  }, [finishWithSession, onNavigate]);

  // Wait for the Firebase session (it survives reloads), then ask where this
  // registration stands.
  useEffect(() => {
    if (!auth) {
      setStep('no-session');
      return undefined;
    }
    return onAuthStateChanged(auth, async (user) => {
      if (!user) {
        setStep('no-session');
        return;
      }
      if (started.current) return;
      started.current = true;
      setFirebaseUser(user);
      try {
        applyState(initialState?.status ? initialState : await getRegistrationState(user, 'register'));
      } catch (err) {
        setMessage({ type: 'error', text: errorMessage(err) });
        setStep('profile');
      }
    });
  }, [initialState, applyState]);

  useEffect(() => {
    if (cooldown <= 0) return undefined;
    const id = setTimeout(() => setCooldown((s) => s - 1), 1000);
    return () => clearTimeout(id);
  }, [cooldown]);

  const run = async (task) => {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    setMessage({ type: '', text: '' });
    try {
      await task();
    } catch (err) {
      setMessage({ type: 'error', text: errorMessage(err) });
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  };

  // ---- Step 1: Complete Your Profile ----
  const handleProfileContinue = (e) => {
    e.preventDefault();
    const found = {};
    const name = fullName.trim();
    const role = designation.trim();
    if (name.length < 3) found.fullName = 'Please enter your full name (at least 3 characters).';
    else if (name.length > 100) found.fullName = 'Please keep your name under 100 characters.';
    if (role.length < 2) found.designation = 'Please enter your designation (e.g. Lecturer, Researcher).';
    else if (role.length > 100) found.designation = 'Please keep your designation under 100 characters.';
    setErrors(found);
    if (Object.keys(found).length) return;

    run(async () => {
      const user = auth.currentUser;
      await updateProfile(user, { displayName: name }).catch(() => {});
      applyState(await saveRegistrationProfile(user, { username: name, designation: role }));
    });
  };

  // ---- Step 2: Set Your Password ----
  const goToVerifyStep = async (user) => {
    await sendVerificationEmail(user, VERIFY_RETURN_PATH);
    setCooldown(RESEND_COOLDOWN_S);
    setStep('verify');
    setMessage({ type: 'success', text: `Verification email sent to ${user.email}.` });
  };

  const handleSetPassword = (e) => {
    e.preventDefault();
    const found = {};
    if (!strong) found.password = 'Your password does not meet all the requirements.';
    else if (password !== confirmPassword) found.confirmPassword = 'Passwords do not match.';
    setErrors(found);
    if (Object.keys(found).length) return;

    run(async () => {
      const user = auth.currentUser;
      if (!hasPasswordSignIn(user)) {
        try {
          await linkPasswordCredential(user, password);
        } catch (err) {
          if (err.code !== 'auth/provider-already-linked') throw err;
        }
      }
      setPassword('');
      setConfirmPassword('');
      // Linking a password can leave the email unverified in Firebase; check the
      // real state before deciding whether to send a verification email.
      await reload(user);
      if (user.emailVerified) applyState(await completeRegistration(user));
      else await goToVerifyStep(user);
    });
  };

  // ---- Step 3: Check Your Email ----
  const checkVerified = useCallback(async ({ silent = false } = {}) => {
    const user = auth.currentUser;
    if (!user) return;
    const verified = await refreshEmailVerified(user); // reload + fresh token
    if (verified) {
      applyState(await completeRegistration(user));
    } else if (!silent) {
      setMessage({
        type: 'error',
        text: 'Your email has not been verified yet. Please check your inbox and Spam/Junk folder, then click the verification link.',
      });
    }
  }, [applyState]);

  const handleIveVerified = () => run(() => checkVerified());

  const handleResend = () => run(async () => {
    const user = auth.currentUser;
    if (!user) {
      setStep('no-session');
      return;
    }
    if (cooldown > 0) return;
    await reload(user);
    if (user.emailVerified) {
      await checkVerified();
      return;
    }
    await sendVerificationEmail(user, VERIFY_RETURN_PATH);
    setCooldown(RESEND_COOLDOWN_S);
    setMessage({ type: 'success', text: 'Verification email sent again. Please check your inbox and Spam/Junk folder.' });
  });

  // Coming back to this tab after clicking the link: check quietly.
  useEffect(() => {
    if (step !== 'verify') return undefined;
    const onFocus = () => { if (!busyRef.current) checkVerified({ silent: true }).catch(() => {}); };
    window.addEventListener('focus', onFocus);
    return () => window.removeEventListener('focus', onFocus);
  }, [step, checkVerified]);

  const useDifferentAccount = async () => {
    await signOut(auth).catch(() => {});
    onNavigate('/register');
  };

  const stepLabel = STEP_NUMBER[step] ? `Step ${STEP_NUMBER[step]} of 3` : '';
  const messageBox = message.text && (
    <p className={`verify-message ${message.type === 'success' ? 'info' : 'error'}`} role={message.type === 'success' ? 'status' : 'alert'}>
      {message.text}
    </p>
  );

  return (
    <div className="verify-page">
      <div className="verify-card reset-card complete-card" role="main">
        {step === 'loading' && (
          <>
            <div className="verify-icon" aria-hidden="true"><i className="bx bx-user-plus" /></div>
            <h1>Complete Your Registration</h1>
            <p className="verify-text" role="status">Loading your account…</p>
          </>
        )}

        {step === 'no-session' && (
          <>
            <div className="verify-icon" aria-hidden="true"><i className="bx bx-user-plus" /></div>
            <h1>Sign in to continue</h1>
            <p className="verify-text">Use Continue with Google on the Register page to resume your registration.</p>
            <div className="verify-actions">
              <button type="button" className="btn" onClick={() => onNavigate('/register')}>Go to Register</button>
            </div>
          </>
        )}

        {step === 'profile' && (
          <form onSubmit={handleProfileContinue} noValidate>
            <div className="verify-icon" aria-hidden="true"><i className="bx bx-user-plus" /></div>
            <p className="complete-step">{stepLabel}</p>
            <h1>Complete Your Profile</h1>
            <p className="verify-text">A few details to finish your ScholarMetrics account.</p>

            <label className="complete-label" htmlFor="cp-name">Full Name</label>
            <div className="input-box">
              <input
                id="cp-name"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                disabled={busy}
                maxLength={100}
                className={errors.fullName ? 'input-invalid' : ''}
                aria-invalid={Boolean(errors.fullName)}
              />
              {errors.fullName && <p className="field-error">{errors.fullName}</p>}
            </div>

            <label className="complete-label" htmlFor="cp-email">Email</label>
            <div className="input-box">
              <input id="cp-email" type="email" value={firebaseUser?.email || ''} readOnly aria-readonly="true" className="complete-readonly" tabIndex={-1} />
            </div>

            <label className="complete-label" htmlFor="cp-designation">Designation</label>
            <div className="input-box">
              <input
                id="cp-designation"
                placeholder="e.g. Lecturer, Researcher"
                value={designation}
                onChange={(e) => setDesignation(e.target.value)}
                disabled={busy}
                maxLength={100}
                autoFocus
                className={errors.designation ? 'input-invalid' : ''}
                aria-invalid={Boolean(errors.designation)}
              />
              {errors.designation && <p className="field-error">{errors.designation}</p>}
            </div>

            {messageBox}

            <div className="verify-actions">
              <button type="submit" className="btn" disabled={busy}>{busy ? 'Saving…' : 'Continue'}</button>
              <button type="button" className="verify-link" onClick={useDifferentAccount} disabled={busy}>
                Not you? Use a different account
              </button>
            </div>
          </form>
        )}

        {step === 'password' && (
          <form onSubmit={handleSetPassword} noValidate>
            <div className="verify-icon" aria-hidden="true"><i className="bx bx-lock-alt" /></div>
            <p className="complete-step">{stepLabel}</p>
            <h1>Set Your Password</h1>
            <p className="verify-text">
              Create a password so you can also sign in with <strong>{firebaseUser?.email}</strong> and a password later.
            </p>

            <div className="input-box">
              <input
                type={showPassword ? 'text' : 'password'}
                className={`has-toggle${errors.password ? ' input-invalid' : ''}`}
                placeholder="Password"
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={busy}
                aria-describedby="cp-password-rules"
              />
              <button type="button" className="password-toggle" onClick={() => setShowPassword((v) => !v)} aria-label={showPassword ? 'Hide password' : 'Show password'}>
                <i className={`bx ${showPassword ? 'bx-hide' : 'bx-show'}`} aria-hidden="true" />
              </button>
            </div>
            <ul id="cp-password-rules" className="password-rules">
              {rules.map((rule) => (
                <li key={rule.id} className={rule.met ? 'met' : ''}>
                  <i className={`bx ${rule.met ? 'bx-check-circle' : 'bx-circle'}`} aria-hidden="true" />
                  {rule.label}
                </li>
              ))}
            </ul>
            {errors.password && <p className="field-error complete-error">{errors.password}</p>}

            <div className="input-box">
              <input
                type={showConfirm ? 'text' : 'password'}
                className={`has-toggle${errors.confirmPassword ? ' input-invalid' : ''}`}
                placeholder="Confirm Password"
                autoComplete="new-password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                disabled={busy}
              />
              <button type="button" className="password-toggle" onClick={() => setShowConfirm((v) => !v)} aria-label={showConfirm ? 'Hide confirm password' : 'Show confirm password'}>
                <i className={`bx ${showConfirm ? 'bx-hide' : 'bx-show'}`} aria-hidden="true" />
              </button>
              {errors.confirmPassword && <p className="field-error">{errors.confirmPassword}</p>}
            </div>

            {messageBox}

            <div className="verify-actions">
              <button type="submit" className="btn" disabled={busy}>{busy ? 'Saving…' : 'Continue'}</button>
              <button type="button" className="btn btn-secondary" onClick={() => { setErrors({}); setMessage({ type: '', text: '' }); setStep('profile'); }} disabled={busy}>
                Back
              </button>
            </div>
          </form>
        )}

        {step === 'verify' && (
          <div>
            <div className="verify-icon reset-icon-success" aria-hidden="true"><i className="bx bx-envelope" /></div>
            <p className="complete-step">{stepLabel}</p>
            <h1>Check your email</h1>
            <p className="verify-text">We've sent a verification email to</p>
            <p className="verify-email">{firebaseUser?.email}</p>
            <p className="verify-text">Please check your inbox and click the verification link to verify your email address.</p>
            <p className="verify-text complete-hint">
              <i className="bx bx-info-circle" aria-hidden="true" /> If you don't see the email, please check your <strong>Spam</strong> or <strong>Junk</strong> folder.
            </p>
            <p className="verify-text">After verifying your email, return here and continue.</p>

            {messageBox}

            <div className="verify-actions">
              <button type="button" className="btn" onClick={handleIveVerified} disabled={busy}>
                {busy ? <><i className="bx bx-loader-alt bx-spin" aria-hidden="true" /> Checking…</> : "I've Verified"}
              </button>
              <button type="button" className="btn btn-secondary" onClick={handleResend} disabled={busy || cooldown > 0}>
                {cooldown > 0 ? `Resend Verification Email (${cooldown}s)` : 'Resend Verification Email'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default CompleteProfile;
