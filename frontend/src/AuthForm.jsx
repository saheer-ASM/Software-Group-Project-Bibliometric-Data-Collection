import React, { useState } from 'react';
import { auth } from './firebase';
import './AuthForm.css';

const AuthForm = ({ onLogin }) => {
  const [isActive, setIsActive] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const [loginUsername, setLoginUsername] = useState('');
  const [loginPassword, setLoginPassword] = useState('');

  const [registerUsername, setRegisterUsername] = useState('');
  const [registerEmail, setRegisterEmail] = useState('');
  const [registerDesignation, setRegisterDesignation] = useState('');
  const [registerPassword, setRegisterPassword] = useState('');
  const [registerConfirmPassword, setRegisterConfirmPassword] = useState('');

  const handleRegisterClick = () => setIsActive(true);
  const handleLoginClick = () => setIsActive(false);

  const handleForgotPassword = async (e) => {
    e.preventDefault();
    if (!loginUsername) {
      setError('Enter your username first, then click Forgot Password');
      return;
    }
    setError('Password reset is not available. Please contact your administrator.');
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

  const handleUnsupportedProvider = (name) => {
    setError(`${name} sign-in is not supported yet`);
  };

  const handleLoginSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await fetch(`${process.env.REACT_APP_API_URL}/api/auth/login`, {
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
      const res = await fetch(`${process.env.REACT_APP_API_URL}/api/auth/register`, {
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
            <span className="input-icon" aria-hidden="true">U</span>
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
            <a href="#forgot" onClick={handleForgotPassword}>Forgot Password?</a>
          </div>
          <button type="submit" className="btn" disabled={loading}>
            {loading ? 'Logging in…' : 'Login'}
          </button>
          <p>or login with social platforms</p>
          <div className="social-icons" aria-label="Social sign-in options">
            <button
              type="button"
              className="social-link google"
              aria-label="Sign in with Google"
              disabled={loading}
              onClick={() => handleSocialLogin('google')}
            >
              <img src="/assets/google.png" alt="" />
            </button>
            <button
              type="button"
              className="social-link microsoft"
              aria-label="Sign in with Microsoft"
              disabled={loading}
              onClick={() => handleUnsupportedProvider('Microsoft')}
            >
              <img src="/assets/microsoft.png" alt="" />
            </button>
            <button
              type="button"
              className="social-link github"
              aria-label="Sign in with GitHub"
              disabled={loading}
              onClick={() => handleSocialLogin('github')}
            >
              <img src="/assets/github.png" alt="" />
            </button>
            <button
              type="button"
              className="social-link linkedin"
              aria-label="Sign in with LinkedIn"
              disabled={loading}
              onClick={() => handleUnsupportedProvider('LinkedIn')}
            >
              <img src="/assets/linkedin.png" alt="" />
            </button>
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
            <span className="input-icon" aria-hidden="true">U</span>
          </div>
          <div className="input-box">
            <input
              type="email"
              placeholder="Email"
              required
              value={registerEmail}
              onChange={(e) => setRegisterEmail(e.target.value)}
            />
            <span className="input-icon" aria-hidden="true">@</span>
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
              type="password"
              placeholder="Password (min 8 chars)"
              required
              minLength={8}
              value={registerPassword}
              onChange={(e) => setRegisterPassword(e.target.value)}
            />
            <span className="input-icon" aria-hidden="true">L</span>
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
            <span className="input-icon" aria-hidden="true">L</span>
          </div>
          <button type="submit" className="btn" disabled={loading}>
            {loading ? 'Registering…' : 'Register'}
          </button>
          <p>or register with social platforms</p>
          <div className="social-icons" aria-label="Social sign-in options">
            <button
              type="button"
              className="social-link google"
              aria-label="Sign in with Google"
              disabled={loading}
              onClick={() => handleSocialLogin('google')}
            >
              <img src="/assets/google.png" alt="" />
            </button>
            <button
              type="button"
              className="social-link microsoft"
              aria-label="Sign in with Microsoft"
              disabled={loading}
              onClick={() => handleUnsupportedProvider('Microsoft')}
            >
              <img src="/assets/microsoft.png" alt="" />
            </button>
            <button
              type="button"
              className="social-link github"
              aria-label="Sign in with GitHub"
              disabled={loading}
              onClick={() => handleSocialLogin('github')}
            >
              <img src="/assets/github.png" alt="" />
            </button>
            <button
              type="button"
              className="social-link linkedin"
              aria-label="Sign in with LinkedIn"
              disabled={loading}
              onClick={() => handleUnsupportedProvider('LinkedIn')}
            >
              <img src="/assets/linkedin.png" alt="" />
            </button>
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