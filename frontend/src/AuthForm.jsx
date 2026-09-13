import React, { useState } from 'react';
import { auth, missingConfig } from './firebase';
import { API_BASE_URL } from './config/api';
import { auth } from './firebase';
import './AuthForm.css';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5001';

const AuthForm = ({ onLogin }) => {
  const [isActive, setIsActive] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // Login fields
  const [loginUsername, setLoginUsername] = useState('');
  const [loginPassword, setLoginPassword] = useState('');

  // Register fields
  const [registerUsername, setRegisterUsername] = useState('');
  const [registerEmail, setRegisterEmail] = useState('');
  const [registerDesignation, setRegisterDesignation] = useState('');
  const [registerPassword, setRegisterPassword] = useState('');
  const [registerConfirmPassword, setRegisterConfirmPassword] = useState('');

  const ensureFirebaseConfig = () => {
    if (missingConfig.length === 0) return true;
    setError('Firebase web config is missing. Fill frontend/.env from Firebase Project settings.');
    return false;
  };

  const exchangeFirebaseToken = async (firebaseUser, profile = {}) => {
    const idToken = await firebaseUser.getIdToken();
    const response = await fetch(`${API_BASE_URL}/api/auth/firebase-login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ idToken, ...profile }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.message || 'Unable to complete account setup');
    localStorage.setItem('token', payload.token);
    return payload.user;
  };

  const handleSocialLogin = async (providerName) => {
    setError('');
    if (!ensureFirebaseConfig()) return;
    setLoading(true);

    let userCredential;
    try {
      if (providerName === 'google') {
        const { GoogleAuthProvider, signInWithPopup } = await import('firebase/auth');
        const provider = new GoogleAuthProvider();
        userCredential = await signInWithPopup(auth, provider);

        const idToken = await userCredential.user.getIdToken();
        const response = await fetch(`${API_BASE_URL}/api/auth/firebase-login`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ idToken }),
        });

        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.message || 'Google sign-in failed');
        }

        localStorage.setItem('token', data.token);
        localStorage.setItem('authProvider', providerName);

        onLogin({
          id: data.user.id,
          username: data.user.username || userCredential.user.displayName || userCredential.user.email?.split('@')[0] || 'User',
          email: data.user.email || userCredential.user.email || '',
          designation: data.user.designation || 'Researcher',
          photoURL: userCredential.user.photoURL || '',
        });
        return;
      } else if (providerName === 'github') {
        const { GithubAuthProvider, signInWithPopup } = await import('firebase/auth');
        const provider = new GithubAuthProvider();
        userCredential = await signInWithPopup(auth, provider);
      } else {
        setError(`${providerName} sign-in is not connected in the app yet.`);
        return;
      }

      const token = await userCredential.user.getIdToken();
      localStorage.setItem('token', token);
      localStorage.setItem('authProvider', providerName);

      const appUser = {
        id: userCredential.user.uid,
        username: userCredential.user.displayName || userCredential.user.email?.split('@')[0] || 'User',
        email: userCredential.user.email || '',
        designation: 'Researcher',
        photoURL: userCredential.user.photoURL || '',
      };

      onLogin(appUser);
    } catch (err) {
      if (providerName === 'google' && userCredential?.user) {
        try {
          const idToken = await userCredential.user.getIdToken();
          localStorage.setItem('token', idToken);
          localStorage.setItem('authProvider', providerName);

          onLogin({
            id: userCredential.user.uid,
            username: userCredential.user.displayName || userCredential.user.email?.split('@')[0] || 'User',
            email: userCredential.user.email || '',
            designation: 'Researcher',
            photoURL: userCredential.user.photoURL || '',
          });
          return;
        } catch {
          // Fall through to the error handling below.
        }
      }

      if (err.code === 'auth/popup-closed-by-user') {
        setError('Sign-in popup was closed before completing login.');
      } else if (err.code === 'auth/account-exists-with-different-credential') {
        setError('An account already exists with this email using another sign-in method.');
      } else {
        setError(err.message || `${providerName} sign-in failed`);
      }
    } finally {
      setLoading(false);
    }
  };
  const handleRegisterClick = () => setIsActive(true);
  const handleLoginClick = () => setIsActive(false);

  const [showForgotPassword, setShowForgotPassword] = useState(false);
  const [forgotEmail, setForgotEmail] = useState('');
  const [forgotMessage, setForgotMessage] = useState('');

  const handleForgotPassword = (e) => {
    e.preventDefault();
    setError('');
    setForgotMessage('');
    setShowForgotPassword(true);
  };

  const handleSendResetEmail = async (e) => {
    e.preventDefault();
    setError('');
    setForgotMessage('');
    setLoading(true);
    try {
      const { sendPasswordResetEmail } = await import('firebase/auth');
      await sendPasswordResetEmail(auth, forgotEmail, {
        url: `${window.location.origin}/reset-password`,
        handleCodeInApp: true,
      });
      setForgotMessage('Reset link sent! Check your email inbox.');
    } catch (err) {
      if (err.code === 'auth/user-not-found') {
        setError('No account found with that email');
      } else if (err.code === 'auth/invalid-email') {
        setError('Enter a valid email address');
      } else {
        setError(err.message || 'Could not send reset email');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleSocialLogin = async (provider) => {
    setError('');
    setLoading(true);
    try {
      const { GoogleAuthProvider, GithubAuthProvider, signInWithPopup } = await import('firebase/auth');
      const prov = provider === 'google' ? new GoogleAuthProvider() : new GithubAuthProvider();
      const result = await signInWithPopup(auth, prov);
      const idToken = await result.user.getIdToken();

      const res = await fetch(`${process.env.REACT_APP_API_URL}/api/auth/social`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ idToken }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.message || `${provider} sign-in failed`);
        return;
      }
      localStorage.setItem('token', data.token);
      onLogin(data.user);
    } catch (err) {
      setError(err.message || `${provider} sign-in failed`);
    } finally {
      setLoading(false);
    }
  };

  const handleLoginSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (!ensureFirebaseConfig()) return;
    setLoading(true);
    try {
      const { signInWithEmailAndPassword } = await import('firebase/auth');
      const userCredential = await signInWithEmailAndPassword(auth, loginEmail, loginPassword);
      const appUser = await exchangeFirebaseToken(userCredential.user);

      onLogin({
        ...appUser,
        photoURL: userCredential.user.photoURL || '',
      const res = await fetch(`${API_BASE_URL}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: loginUsername, password: loginPassword }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.message || 'Login failed');
        return;
      }
      localStorage.setItem('token', data.token);
      onLogin(data.user);
    } catch {
      setError('Network error. Is the server running?');
    } finally {
      setLoading(false);
    }
  };

  const handleRegisterSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (registerPassword.length < 8) {
      setError('Password must be at least 8 characters');
      return;
    }
    if (registerPassword !== registerConfirmPassword) {
      setError('Passwords do not match');
      return;
    }
    setLoading(true);
    try {
      const { createUserWithEmailAndPassword, updateProfile, deleteUser } = await import('firebase/auth');
      
      const userCredential = await createUserWithEmailAndPassword(auth, registerEmail, registerPassword);
      
      await updateProfile(userCredential.user, {
        displayName: registerUsername,
      });

      let appUser;
      try {
        appUser = await exchangeFirebaseToken(userCredential.user, {
          username: registerUsername,
          designation: registerDesignation,
        });
      } catch (setupError) {
        await deleteUser(userCredential.user).catch(() => {});
        throw setupError;
      }
      
      onLogin({
        ...appUser,
        photoURL: '',
      });
    } catch (err) {
      if (err.code === 'auth/email-already-in-use') {
        setError('An account already exists with this email address.');
      } else if (err.code === 'auth/invalid-email') {
        setError('Please enter a valid email address.');
      } else {
        setError(err.message || 'Registration failed');
      }
      const res = await fetch(`${API_BASE_URL}/api/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: registerUsername,
          email: registerEmail,
          designation: registerDesignation,
          password: registerPassword,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.message || 'Registration failed');
        return;
      }
      localStorage.setItem('token', data.token);
      onLogin(data.user);
    } catch {
      setError('Network error. Is the server running?');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={`container ${isActive ? 'active' : ''}`}>
      {error && (
        <div style={{
          position: 'fixed', top: 16, left: '50%', transform: 'translateX(-50%)',
          background: '#ff4d4f', color: '#fff', padding: '10px 24px',
          borderRadius: 8, zIndex: 9999, fontWeight: 500
        }}>
          {error}
        </div>
      )}

      {showForgotPassword && (
        <div
          style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 10000,
          }}
          onClick={() => setShowForgotPassword(false)}
        >
          <div
            style={{ background: '#fff', borderRadius: 12, padding: 32, width: 340, boxShadow: '0 10px 40px rgba(0,0,0,0.2)' }}
            onClick={(e) => e.stopPropagation()}
          >
            <h2 style={{ marginTop: 0 }}>Reset Password</h2>
            {forgotMessage ? (
              <>
                <p>{forgotMessage}</p>
                <button type="button" className="btn" onClick={() => setShowForgotPassword(false)}>Close</button>
              </>
            ) : (
              <form onSubmit={handleSendResetEmail}>
                <p>Enter your account email and we'll send you a link to reset your password.</p>
                <div className="input-box">
                  <input
                    type="email"
                    placeholder="Email"
                    required
                    value={forgotEmail}
                    onChange={(e) => setForgotEmail(e.target.value)}
                  />
                  <i className='bx bxs-envelope'></i>
                </div>
                <button type="submit" className="btn" disabled={loading} style={{ marginTop: 12 }}>
                  {loading ? 'Sending…' : 'Send Reset Link'}
                </button>
                <button
                  type="button"
                  className="btn"
                  style={{ marginTop: 8, background: 'transparent', color: '#1b3d6d', border: '1px solid #1b3d6d' }}
                  onClick={() => setShowForgotPassword(false)}
                >
                  Cancel
                </button>
              </form>
            )}
          </div>
        </div>
      )}

      {/* Login Form */}
      <div className="form-box login">
        <form onSubmit={handleLoginSubmit}>
          <h1>Login</h1>
          <div className="input-box">
            <input
              type="text"
              placeholder="Username"
              required
              value={loginUsername}
              onChange={(e) => setLoginUsername(e.target.value)}
            />
            <i className='bx bxs-user'></i>
          </div>
          <div className="input-box">
            <input
              type="password"
              placeholder="Password"
              required
              value={loginPassword}
              onChange={(e) => setLoginPassword(e.target.value)}
            />
            <i className='bx bxs-lock-alt'></i>
          </div>
          <div className="forgot-link">
            <a href="#forgot" onClick={handleForgotPassword}>Forgot Password?</a>
          </div>
          <button type="submit" className="btn" disabled={loading}>
            {loading ? 'Logging in…' : 'Login'}
          </button>
          <p>or login with social platforms</p>
          <div className="social-icons">
            <button type="button" onClick={() => handleSocialLogin('google')} disabled={loading}><i className='bx bxl-google'></i></button>
            <button type="button" onClick={() => handleSocialLogin('github')} disabled={loading}><i className='bx bxl-github'></i></button>
          </div>
        </form>
      </div>

      {/* Register Form */}
      <div className="form-box register">
        <form onSubmit={handleRegisterSubmit}>
          <h1>Registration</h1>
          <div className="input-box">
            <input
              type="text"
              placeholder="Full Name"
              required
              value={registerUsername}
              onChange={(e) => setRegisterUsername(e.target.value)}
            />
            <i className='bx bxs-user'></i>
          </div>
          <div className="input-box">
            <input
              type="email"
              placeholder="Email"
              required
              value={registerEmail}
              onChange={(e) => setRegisterEmail(e.target.value)}
            />
            <i className='bx bxs-envelope'></i>
          </div>
          <div className="input-box">
            <input
              type="text"
              placeholder="Designation"
              required
              value={registerDesignation}
              onChange={(e) => setRegisterDesignation(e.target.value)}
            />
            <i className='bx bxs-briefcase'></i>
          </div>
          <div className="input-box">
            <input
              type="password"
              placeholder="Password (min 8 chars)"
              required
              minLength={8}
              value={registerPassword}
              onChange={(e) => setRegisterPassword(e.target.value)}
            />
            <i className='bx bxs-lock-alt'></i>
          </div>
          <div className="input-box">
            <input
              type="password"
              placeholder="Confirm Password"
              required
              minLength={8}
              value={registerConfirmPassword}
              onChange={(e) => setRegisterConfirmPassword(e.target.value)}
            />
            <i className='bx bxs-lock-alt'></i>
          </div>
          <button type="submit" className="btn" disabled={loading}>
            {loading ? 'Registering…' : 'Register'}
          </button>
          <p>or register with social platforms</p>
          <div className="social-icons">
            <button type="button" onClick={() => handleSocialLogin('google')} disabled={loading}><i className='bx bxl-google'></i></button>
            <button type="button" onClick={() => handleSocialLogin('github')} disabled={loading}><i className='bx bxl-github'></i></button>
          </div>
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
