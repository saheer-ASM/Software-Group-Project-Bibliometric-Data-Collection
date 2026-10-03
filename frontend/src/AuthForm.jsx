import React, { useEffect, useState } from 'react';
import {
  auth,
  missingConfig,
  registerWithEmail,
  sendVerificationEmail,
  signInWithGoogle,
  googleCredentialFromError,
} from './firebase';
import { API_BASE_URL } from './config/api';
import { sanitizeEmail, isValidEmail, checkPassword } from './authValidation';
import { authErrorMessage } from './authErrors';
import { RESEND_COOLDOWN_S, getRegistrationState } from './services/registrationService';
import './AuthForm.css';

// mode: 'login' | 'register' | 'forgot' (the /login, /register and /forgot-password URLs in App.js)
// notice: optional success message, e.g. after email verification
const AuthForm = ({ onLogin, mode = 'login', onNavigate, notice = '' }) => {
  const isActive = mode === 'register';
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');

  const [registerUsername, setRegisterUsername] = useState('');
  const [registerEmail, setRegisterEmail] = useState('');
  const [registerDesignation, setRegisterDesignation] = useState('');
  const [registerPassword, setRegisterPassword] = useState('');
  const [registerConfirmPassword, setRegisterConfirmPassword] = useState('');
  const [registerEmailTouched, setRegisterEmailTouched] = useState(false);
  const [showRegisterPassword, setShowRegisterPassword] = useState(false);
  const [showRegisterConfirmPassword, setShowRegisterConfirmPassword] = useState(false);

  const registerEmailInvalid = registerEmailTouched && registerEmail.trim() !== '' && !isValidEmail(registerEmail);
  const { rules: passwordChecks, strong: passwordStrong } = checkPassword(registerPassword);

  // Set when Google sign-in hits an existing email/password account that Firebase
  // did not link automatically. Holds the Google credential until the user proves
  // ownership of the existing account with its password, then it is linked to
  // that SAME Firebase user (no second account).
  const [pendingGoogleLink, setPendingGoogleLink] = useState(null); // { email, credential }

  // Sign In result that needs explaining instead of a session:
  // { kind: 'not-registered' } | { kind: 'incomplete' | 'verify', email, registration }
  const [accountNotice, setAccountNotice] = useState(null);
  const [noticeMessage, setNoticeMessage] = useState('');
  const [resendCooldown, setResendCooldown] = useState(0);

  useEffect(() => {
    if (resendCooldown <= 0) return undefined;
    const id = setTimeout(() => setResendCooldown((s) => s - 1), 1000);
    return () => clearTimeout(id);
  }, [resendCooldown]);

  // Leaving the Sign In panel clears its notice.
  useEffect(() => {
    if (mode !== 'login') setAccountNotice(null);
  }, [mode]);

  // Forgot Password lives inside the login panel at /forgot-password (mode 'forgot'):
  // null = Sign In form, 'form' = enter email, 'sent' = "Check your email".
  const [resetSent, setResetSent] = useState(false);
  const forgotStep = mode === 'forgot' ? (resetSent ? 'sent' : 'form') : null;
  const [resetEmail, setResetEmail] = useState('');
  const [resetError, setResetError] = useState('');
  const [resetSending, setResetSending] = useState(false);

  // Coming back to /forgot-password later starts with a fresh form.
  useEffect(() => {
    if (mode !== 'forgot') {
      setResetSent(false);
      setResetError('');
    }
  }, [mode]);

  const ensureFirebaseConfig = () => {
    if (missingConfig.length === 0) return true;
    setError('Firebase web config is missing. Fill frontend/.env from Firebase Project settings.');
    return false;
  };

  // What a successful Firebase sign-in means for ScholarMetrics. Firebase
  // Authentication and ScholarMetrics registration are separate: the backend
  // checks the profile + Firebase state and answers with a status.
  //   intent 'register' (Register page): may start / resume a registration.
  //   intent 'signin'   (Sign In page):  never starts one; explains instead.
  const resolveAccount = async (firebaseUser, intent, viaGoogle = false) => {
    const { signOut } = await import('firebase/auth');
    const data = await getRegistrationState(firebaseUser, intent);
    switch (data.status) {
      case 'COMPLETED':
        localStorage.setItem('token', data.token);
        onLogin({ ...data.user, photoURL: firebaseUser.photoURL || '' });
        return;
      case 'COMPLETED_UNVERIFIED':
        // Finished email/password registration waiting for its verification link.
        onNavigate('/verify-email', { notice: 'Please verify your email address before logging in.' });
        return;
      case 'NOT_REGISTERED':
        await signOut(auth).catch(() => {});
        setAccountNotice({ kind: 'not-registered', viaGoogle });
        return;
      default: // INCOMPLETE | VERIFICATION_PENDING
        if (intent === 'register') {
          onNavigate('/complete-profile', { registration: data });
          return;
        }
        // Keep the Firebase session so "Continue Registration" can resume.
        setAccountNotice({
          kind: data.status === 'VERIFICATION_PENDING' ? 'verify' : 'incomplete',
          email: firebaseUser.email,
          registration: data,
        });
    }
  };

  const continueRegistration = () => {
    onNavigate('/complete-profile', { registration: accountNotice?.registration });
  };

  const resendFromNotice = async () => {
    const user = auth.currentUser;
    if (!user || resendCooldown > 0) return;
    setNoticeMessage('');
    try {
      const { reload } = await import('firebase/auth');
      await reload(user);
      if (user.emailVerified) {
        setNoticeMessage('Your email is already verified. Continue your registration to finish.');
        return;
      }
      await sendVerificationEmail(user, '/complete-profile');
      setResendCooldown(RESEND_COOLDOWN_S);
      setNoticeMessage('Verification email sent again. Please check your inbox and Spam/Junk folder.');
    } catch (err) {
      setNoticeMessage(authErrorMessage(err, 'Could not send the verification email. Please try again.'));
    }
  };

  // Stores Full Name + Designation for a newly created (unverified) Firebase
  // account. The backend does not start a session until the email is verified.
  const saveRegistrationProfile = async (firebaseUser, profile) => {
    const idToken = await firebaseUser.getIdToken();
    const response = await fetch(`${API_BASE_URL}/api/auth/register-profile`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ idToken, ...profile }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.message || 'Could not save your registration details');
  };

  // Continue with Google. Three cases, all ending on ONE Firebase user per email:
  //  - Google-first user: Firebase creates the account; the backend creates the
  //    profile on first login (Google has already verified the email).
  //  - Existing email/password account that Firebase links automatically (Google
  //    is the trusted provider for that email): same uid, Google is added to it.
  //  - Existing account Firebase will not auto-link
  //    (auth/account-exists-with-different-credential): keep the Google credential,
  //    ask for the account password, then link it with linkWithCredential().
  const handleGoogleLogin = async (intent) => {
    setError('');
    setAccountNotice(null);
    setNoticeMessage('');
    if (!ensureFirebaseConfig()) return;
    setLoading(true);

    const { signOut } = await import('firebase/auth');
    let userCredential;
    try {
      userCredential = await signInWithGoogle();
      await resolveAccount(userCredential.user, intent, true);
    } catch (err) {
      if (err.code === 'auth/account-exists-with-different-credential') {
        const credential = googleCredentialFromError(err);
        const email = sanitizeEmail(err.customData?.email || '');
        if (credential) {
          setPendingGoogleLink({ email, credential });
          if (email) setLoginEmail(email);
          setLoginPassword('');
          return;
        }
      }
      // Backend refused (or anything else failed): leave nothing signed in.
      if (userCredential?.user) await signOut(auth).catch(() => {});
      setError(authErrorMessage(err, err.message || 'Google sign-in failed. Please try again.'));
    } finally {
      setLoading(false);
    }
  };

  const openForgotPassword = (e) => {
    e.preventDefault();
    setError('');
    setResetError('');
    setResetEmail(loginEmail.trim());
    onNavigate('/forgot-password');
  };

  const backToSignIn = () => {
    setResetError('');
    onNavigate('/login');
  };

  const handleSendReset = async (e) => {
    e.preventDefault();
    if (resetSending) return;
    setResetError('');
    if (!ensureFirebaseConfig()) return;

    const cleanEmail = sanitizeEmail(resetEmail);
    if (!cleanEmail) {
      setResetError('Please enter your email address.');
      return;
    }
    if (!isValidEmail(cleanEmail)) {
      setResetError('Please enter a valid email address (e.g. name@example.com).');
      return;
    }

    setResetSending(true);
    try {
      const { sendPasswordResetEmail } = await import('firebase/auth');
      await sendPasswordResetEmail(auth, cleanEmail);
      setResetEmail(cleanEmail);
      setResetSent(true);
    } catch (err) {
      const known = ['auth/user-not-found', 'auth/invalid-email', 'auth/missing-email',
        'auth/too-many-requests', 'auth/network-request-failed'];
      setResetError(known.includes(err.code)
        ? authErrorMessage(err)
        : 'Unable to send the password reset email. Please check the email address and try again.');
    } finally {
      setResetSending(false);
    }
  };

  const handleRegisterClick = () => {
    setError('');
    onNavigate('/register');
  };

  const handleLoginClick = () => {
    setError('');
    onNavigate('/login');
  };

  const handleLoginSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setAccountNotice(null);
    setNoticeMessage('');
    if (!ensureFirebaseConfig()) return;
    setLoading(true);
    try {
      const { signInWithEmailAndPassword, linkWithCredential } = await import('firebase/auth');
      const email = sanitizeEmail(loginEmail);
      const userCredential = await signInWithEmailAndPassword(auth, email, loginPassword);

      // Finish a pending "Continue with Google": link the Google credential to
      // this same account so both sign-in methods work from now on.
      if (pendingGoogleLink && (!pendingGoogleLink.email || pendingGoogleLink.email === email)) {
        try {
          await linkWithCredential(userCredential.user, pendingGoogleLink.credential);
          await userCredential.user.getIdToken(true);
        } catch (linkErr) {
          if (linkErr.code !== 'auth/provider-already-linked') throw linkErr;
        }
        setPendingGoogleLink(null);
      }

      // Completed -> Dashboard; unverified email/password account -> /verify-email;
      // unfinished Google registration -> explained above the form.
      await resolveAccount(userCredential.user, 'signin');
    } catch (err) {
      if (err.code === 'EMAIL_NOT_VERIFIED') {
        onNavigate('/verify-email', { notice: 'Please verify your email address before logging in.' });
      } else {
        setError(authErrorMessage(err, err.message || 'Login failed. Please try again.'));
      }
    } finally {
      setLoading(false);
    }
  };

  const handleRegisterSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (!ensureFirebaseConfig()) return;

    if (!registerUsername.trim() || !registerEmail.trim() || !registerDesignation.trim() || !registerPassword || !registerConfirmPassword) {
      setError('All fields are required');
      return;
    }
    const cleanEmail = sanitizeEmail(registerEmail);
    if (!isValidEmail(cleanEmail)) {
      setRegisterEmailTouched(true);
      setError('Please enter a valid email address (e.g. name@example.com).');
      return;
    }
    if (!passwordStrong) {
      setError('Password must have at least 8 characters, an uppercase letter, a lowercase letter, a number and a special character.');
      return;
    }
    if (registerPassword !== registerConfirmPassword) {
      setError('Passwords do not match');
      return;
    }
    setLoading(true);
    try {
      const { updateProfile, deleteUser } = await import('firebase/auth');

      // 1. Firebase Authentication owns the email + password.
      const userCredential = await registerWithEmail(cleanEmail, registerPassword);
      const firebaseUser = userCredential.user;

      // 2. Save Full Name + Designation in our user store. If that fails, remove the
      //    Firebase account so the user can simply try registering again.
      try {
        await updateProfile(firebaseUser, { displayName: registerUsername.trim() });
        await saveRegistrationProfile(firebaseUser, {
          username: registerUsername.trim(),
          designation: registerDesignation.trim(),
        });
      } catch (setupError) {
        await deleteUser(firebaseUser).catch(() => {});
        throw setupError;
      }

      // 3. Send the verification email. The account stays unverified (no backend
      //    session) until the link in that email is clicked.
      let sendError = '';
      try {
        await sendVerificationEmail(firebaseUser);
      } catch (mailError) {
        sendError = mailError.code === 'auth/too-many-requests'
          ? 'Too many requests, so the verification email was not sent. Wait a few minutes, then use "Resend Verification Email".'
          : 'We could not send the verification email. Use "Resend Verification Email" to try again.';
      }

      onNavigate('/verify-email', sendError ? { error: sendError } : {});
    } catch (err) {
      setError(authErrorMessage(err, err.message || 'Registration failed. Please try again.'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={`container ${isActive ? 'active' : ''}`}>
      {notice && !error && (
        <div className="auth-notice" role="status">{notice}</div>
      )}
      {error && (
        <div style={{
          position: 'fixed', top: 16, left: '50%', transform: 'translateX(-50%)',
          background: '#ff4d4f', color: '#fff', padding: '10px 24px',
          borderRadius: 8, zIndex: 9999, fontWeight: 500
        }}>
          {error}
        </div>
      )}

      {/* Login Form */}
      <div className="form-box login">
        {forgotStep === 'form' && (
          <form className="forgot-view" onSubmit={handleSendReset} noValidate>
            <h1>Reset Password</h1>
            <p>Enter the email address you use for ScholarMetrics and we'll send you a link to reset your password.</p>
            <div className="input-box">
              <input
                type="email"
                placeholder="Email"
                autoFocus
                value={resetEmail}
                onChange={(e) => { setResetEmail(e.target.value); if (resetError) setResetError(''); }}
                disabled={resetSending}
                className={resetError ? 'input-invalid' : ''}
                aria-invalid={Boolean(resetError)}
                aria-describedby="reset-email-error"
              />
              {resetError && <p id="reset-email-error" className="field-error" role="alert">{resetError}</p>}
            </div>
            <button type="submit" className="btn" disabled={resetSending}>
              {resetSending ? 'Sending…' : 'Send Reset Link'}
            </button>
            <button type="button" className="forgot-back-link" onClick={backToSignIn} disabled={resetSending}>
              <i className="bx bx-arrow-back" aria-hidden="true" /> Back to Sign In
            </button>
          </form>
        )}

        {forgotStep === 'sent' && (
          <div className="forgot-view forgot-sent" role="status">
            <div className="forgot-sent-icon" aria-hidden="true"><i className="bx bx-check" /></div>
            <h1>Check your email</h1>
            <p className="forgot-sent-text">We've sent a password reset link to</p>
            <p className="forgot-sent-email">{resetEmail}</p>
            <p className="forgot-sent-text">Please check your inbox and follow the instructions to reset your password.</p>
            <button type="button" className="btn" onClick={backToSignIn}>Back to Sign In</button>
          </div>
        )}

        {forgotStep === null && (
        <form onSubmit={handleLoginSubmit}>
          <h1>Login</h1>
          {accountNotice && (
            <div className={`account-notice account-notice-${accountNotice.kind}`} role="status">
              {accountNotice.kind === 'not-registered' && (
                <>
                  <p className="account-notice-title"><i className="bx bx-user-x" aria-hidden="true" /> No ScholarMetrics account found.</p>
                  <p>This {accountNotice.viaGoogle ? 'Google account' : 'account'} is not registered with ScholarMetrics. Please create an account first.</p>
                  <div className="account-notice-actions">
                    <button type="button" className="account-notice-primary" onClick={() => { setAccountNotice(null); onNavigate('/register'); }}>Create Account</button>
                  </div>
                </>
              )}
              {accountNotice.kind === 'incomplete' && (
                <>
                  <p className="account-notice-title"><i className="bx bx-error-circle" aria-hidden="true" /> Your registration is not complete.</p>
                  <p>Please complete your registration and verify your email address before signing in.</p>
                  <div className="account-notice-actions">
                    <button type="button" className="account-notice-primary" onClick={continueRegistration}>Continue Registration</button>
                  </div>
                </>
              )}
              {accountNotice.kind === 'verify' && (
                <>
                  <p className="account-notice-title"><i className="bx bx-envelope" aria-hidden="true" /> Email verification required.</p>
                  <p>We've sent a verification email to <strong>{accountNotice.email}</strong>.</p>
                  <p>Please check your inbox and <strong>Spam/Junk</strong> folder, then click the verification link.</p>
                  {noticeMessage && <p className="account-notice-message">{noticeMessage}</p>}
                  <div className="account-notice-actions">
                    <button type="button" className="account-notice-secondary" onClick={resendFromNotice} disabled={resendCooldown > 0}>
                      {resendCooldown > 0 ? `Resend Verification Email (${resendCooldown}s)` : 'Resend Verification Email'}
                    </button>
                    <button type="button" className="account-notice-primary" onClick={continueRegistration}>Continue Registration</button>
                  </div>
                </>
              )}
            </div>
          )}
          {pendingGoogleLink && (
            <div className="link-prompt" role="status">
              <p>
                An account already exists for <strong>{pendingGoogleLink.email || 'this email'}</strong>.
                Enter its password to link your Google account. After that you can use either method.
              </p>
              <button type="button" onClick={() => setPendingGoogleLink(null)}>Cancel</button>
            </div>
          )}
          <div className="input-box">
            <input
              type="email"
              placeholder="Email"
              required
              value={loginEmail}
              onChange={(e) => setLoginEmail(e.target.value)}
            />
            <span className="input-icon" aria-hidden="true">@</span>
          </div>
          <div className="input-box">
            <input
              type="password"
              placeholder="Password"
              required
              value={loginPassword}
              onChange={(e) => setLoginPassword(e.target.value)}
            />
            <span className="input-icon" aria-hidden="true">L</span>
          </div>
          <div className="forgot-link">
            <a href="/forgot-password" onClick={openForgotPassword}>Forgot Password?</a>
          </div>
          <button type="submit" className="btn" disabled={loading}>
            {loading ? 'Logging in…' : pendingGoogleLink ? 'Login & Link Google' : 'Login'}
          </button>
          <div className="auth-divider" role="separator"><span>OR</span></div>
          <button
            type="button"
            className="google-btn"
            disabled={loading || missingConfig.length > 0}
            title={missingConfig.length > 0 ? 'Firebase not configured' : undefined}
            onClick={() => handleGoogleLogin('signin')}
          >
            <img src="/assets/google.png" alt="" aria-hidden="true" />
            <span>Continue with Google</span>
          </button>
        </form>
        )}
      </div>

      {/* Register Form */}
      <div className="form-box register">
        <form onSubmit={handleRegisterSubmit} noValidate>
          <h1>Registration</h1>
          <div className="input-box">
            <input
              type="text"
              placeholder="Full Name"
              required
              value={registerUsername}
              onChange={(e) => setRegisterUsername(e.target.value)}
            />
            <span className="input-icon" aria-hidden="true">U</span>
          </div>
          <div className="input-box">
            <input
              type="email"
              placeholder="Email"
              required
              value={registerEmail}
              onChange={(e) => setRegisterEmail(e.target.value)}
              onBlur={() => {
                setRegisterEmailTouched(true);
                setRegisterEmail((value) => sanitizeEmail(value));
              }}
              className={registerEmailInvalid ? 'input-invalid' : ''}
              aria-invalid={registerEmailInvalid}
              aria-describedby="register-email-error"
            />
            <span className="input-icon" aria-hidden="true">@</span>
            {registerEmailInvalid && (
              <p id="register-email-error" className="field-error">
                Enter a valid email address, e.g. name@example.com
              </p>
            )}
          </div>
          <div className="input-box">
            <input
              type="text"
              placeholder="Designation"
              required
              value={registerDesignation}
              onChange={(e) => setRegisterDesignation(e.target.value)}
            />
            <span className="input-icon" aria-hidden="true">D</span>
          </div>
          <div className="input-box">
            <input
              type={showRegisterPassword ? 'text' : 'password'}
              placeholder="Password (min 8 chars)"
              className="has-toggle"
              required
              minLength={8}
              value={registerPassword}
              onChange={(e) => setRegisterPassword(e.target.value)}
              aria-describedby="register-password-rules"
            />
            <span className="input-icon" aria-hidden="true">L</span>
            <button
              type="button"
              className="password-toggle"
              onClick={() => setShowRegisterPassword((v) => !v)}
              aria-label={showRegisterPassword ? 'Hide password' : 'Show password'}
            >
              <i className={`bx ${showRegisterPassword ? 'bx-hide' : 'bx-show'}`} aria-hidden="true" />
            </button>
          </div>
          {registerPassword && (
            <ul id="register-password-rules" className="password-rules">
              {passwordChecks.map((rule) => (
                <li key={rule.id} className={rule.met ? 'met' : ''}>
                  <i className={`bx ${rule.met ? 'bx-check-circle' : 'bx-circle'}`} aria-hidden="true" />
                  {rule.label}
                </li>
              ))}
            </ul>
          )}
          <div className="input-box">
            <input
              type={showRegisterConfirmPassword ? 'text' : 'password'}
              placeholder="Confirm Password"
              className="has-toggle"
              required
              minLength={8}
              value={registerConfirmPassword}
              onChange={(e) => setRegisterConfirmPassword(e.target.value)}
            />
            <span className="input-icon" aria-hidden="true">L</span>
            <button
              type="button"
              className="password-toggle"
              onClick={() => setShowRegisterConfirmPassword((v) => !v)}
              aria-label={showRegisterConfirmPassword ? 'Hide confirm password' : 'Show confirm password'}
            >
              <i className={`bx ${showRegisterConfirmPassword ? 'bx-hide' : 'bx-show'}`} aria-hidden="true" />
            </button>
          </div>
          <button type="submit" className="btn" disabled={loading}>
            {loading ? 'Registering…' : 'Register'}
          </button>
          <div className="auth-divider" role="separator"><span>OR</span></div>
          <button
            type="button"
            className="google-btn"
            disabled={loading || missingConfig.length > 0}
            title={missingConfig.length > 0 ? 'Firebase not configured' : undefined}
            onClick={() => handleGoogleLogin('register')}
          >
            <img src="/assets/google.png" alt="" aria-hidden="true" />
            <span>Continue with Google</span>
          </button>
        </form>
      </div>

      {/* Toggle Box */}
      <div className="toggle-box">
        <div className="toggle-panel toggle-left">
          <h1>Hello, Welcome!</h1>
          <p>Don't have an account?</p>
          <button className="btn register-btn" onClick={handleRegisterClick}>Register</button>
        </div>

        <div className="toggle-panel toggle-right">
          <h1>Welcome Back!</h1>
          <p>Already have an account?</p>
          <button className="btn login-btn" onClick={handleLoginClick}>Login</button>
        </div>
      </div>
    </div>
  );
};

export default AuthForm;
