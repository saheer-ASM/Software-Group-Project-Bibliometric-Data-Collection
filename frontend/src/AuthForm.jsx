import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { auth, firestore, missingConfig } from './firebase';
import './AuthForm.css';

const AuthForm = ({ onLogin }) => {
  const navigate = useNavigate();
  const [isActive, setIsActive] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const [loginEmail, setLoginEmail] = useState('');
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
    setError('');
    setIsActive(true);
  };

  const handleLoginClick = () => {
    setError('');
    setIsActive(false);
  };

  const handleLoginSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const { signInWithEmailAndPassword } = await import('firebase/auth');
      const { doc, getDoc, getFirestore } = await import('firebase/firestore');
      
      const userCredential = await signInWithEmailAndPassword(auth, loginEmail, loginPassword);
      const token = await userCredential.user.getIdToken();
      localStorage.setItem('token', token);
      
      // Attempt to fetch designation from Firestore if available
      let designation = 'Researcher';
      let username = userCredential.user.displayName || userCredential.user.email?.split('@')[0] || 'User';
      
      try {
        const userDoc = await getDoc(doc(getFirestore(), 'users', userCredential.user.uid));
        if (userDoc.exists()) {
          const userData = userDoc.data();
          if (userData.designation) designation = userData.designation;
          if (userData.username) username = userData.username;
        }
      } catch (firestoreErr) {
        console.warn('Could not fetch user document:', firestoreErr);
      }

      onLogin({
        id: userCredential.user.uid,
        username,
        email: userCredential.user.email || '',
        designation,
        photoURL: userCredential.user.photoURL || '',
      });
    } catch (err) {
      if (err.code === 'auth/invalid-credential') {
        setError('Invalid email or password.');
      } else {
        setError(err.message || 'Login failed');
      }
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
              disabled={loading || missingConfig.length > 0}
              title={missingConfig.length > 0 ? 'Firebase not configured' : ''}
              onClick={() => handleSocialLogin('google')}
            >
              <img src="/assets/google.png" alt="" />
            </button>
            <button
              type="button"
              className="social-link microsoft"
              aria-label="Sign in with Microsoft"
              disabled={true}
              title="Not connected yet"
              onClick={() => handleUnsupportedProvider('Microsoft')}
            >
              <img src="/assets/microsoft.png" alt="" />
            </button>
            <button
              type="button"
              className="social-link github"
              aria-label="Sign in with GitHub"
              disabled={loading || missingConfig.length > 0}
              title={missingConfig.length > 0 ? 'Firebase not configured' : ''}
              onClick={() => handleSocialLogin('github')}
            >
              <img src="/assets/github.png" alt="" />
            </button>
            <button
              type="button"
              className="social-link linkedin"
              aria-label="Sign in with LinkedIn"
              disabled={true}
              title="Not connected yet"
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
              disabled={loading || missingConfig.length > 0}
              title={missingConfig.length > 0 ? 'Firebase not configured' : ''}
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
              disabled={loading || missingConfig.length > 0}
              title={missingConfig.length > 0 ? 'Firebase not configured' : ''}
              onClick={() => handleSocialLogin('github')}
            >
              <img src="/assets/github.png" alt="" />
            </button>
            <button
              type="button"
              className="social-link linkedin"
              aria-label="Sign in with LinkedIn"
              disabled={true}
              title="Not connected yet"
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