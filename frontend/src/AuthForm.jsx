import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { auth, firestore, missingConfig } from './firebase';
import './AuthForm.css';

const AuthForm = ({ onLogin }) => {
  const navigate = useNavigate();
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

  const ensureFirebaseConfig = () => {
    if (missingConfig.length === 0) return true;
    setError('Firebase web config is missing. Fill frontend/.env from Firebase Project settings.');
    return false;
  };

  const handleSocialLogin = async (providerName) => {
    setError('');
    if (!ensureFirebaseConfig()) return;

    try {
      let userCredential;
      if (providerName === 'google') {
        const { GoogleAuthProvider, signInWithPopup } = await import('firebase/auth');
        const provider = new GoogleAuthProvider();
        userCredential = await signInWithPopup(auth, provider);
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

  const handleUnsupportedProvider = (providerName) => {
    setError(`${providerName} sign-in is not connected in the app yet.`);
  };

  const handleForgotPassword = async (e) => {
    e.preventDefault();
    setError('');
    if (!ensureFirebaseConfig()) return;

    const email = window.prompt('Enter the email address for password reset:');
    const cleanEmail = String(email || '').trim();

    if (!cleanEmail) {
      setError('Please enter an email address to reset your password.');
      return;
    }

    setLoading(true);
    try {
      const { sendPasswordResetEmail } = await import('firebase/auth');
      await sendPasswordResetEmail(auth, cleanEmail);
      setError(`Password reset email sent to ${cleanEmail}. Please check the inbox.`);
    } catch (err) {
      if (err.code === 'auth/invalid-email') {
        setError('Please enter a valid email address.');
      } else {
        setError(err.message || 'Could not send password reset email.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleRegisterClick = () => {
    setIsActive(true);
  };

  const handleLoginClick = () => {
    setIsActive(false);
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

    if (registerPassword.length < 8) {
      alert('Password must be at least 8 characters');
      return;
    }

    if (registerPassword !== registerConfirmPassword) {
      alert('Passwords do not match');
      return;
    }

    try {
      const { createUserWithEmailAndPassword, updateProfile } = await import('firebase/auth');
      const { doc, setDoc, getFirestore } = await import('firebase/firestore');
      
      const userCredential = await createUserWithEmailAndPassword(auth, registerEmail, registerPassword);
      
      await updateProfile(userCredential.user, {
        displayName: registerUsername,
      });

      await setDoc(doc(getFirestore(), 'users', userCredential.user.uid), {
        username: registerUsername,
        email: registerEmail,
        designation: registerDesignation,
        createdAt: new Date(),
      });

      const token = await userCredential.user.getIdToken();
      localStorage.setItem('token', token);
      
      onLogin({
        id: userCredential.user.uid,
        username: registerUsername,
        email: registerEmail,
        designation: registerDesignation,
        photoURL: '',
      });
    } catch (err) {
      setError(err.message || 'Registration failed');
    }
  };

  return (
    <div className={`container ${isActive ? 'active' : ''}`}>
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
          <button type="submit" className="btn">Login</button>
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
          <button type="submit" className="btn">Register</button>
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