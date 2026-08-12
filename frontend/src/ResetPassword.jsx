import React, { useEffect, useState } from 'react';
import { auth } from './firebase';
import './AuthForm.css';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5001';

const ResetPassword = ({ onLogin }) => {
  const [oobCode, setOobCode] = useState('');
  const [email, setEmail] = useState('');
  const [status, setStatus] = useState('verifying'); // verifying | ready | invalid | done
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get('oobCode');
    if (!code) {
      setStatus('invalid');
      return;
    }
    setOobCode(code);

    (async () => {
      try {
        const { verifyPasswordResetCode } = await import('firebase/auth');
        const resolvedEmail = await verifyPasswordResetCode(auth, code);
        setEmail(resolvedEmail);
        setStatus('ready');
      } catch {
        setStatus('invalid');
      }
    })();
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (newPassword.length < 8) {
      setError('Password must be at least 8 characters');
      return;
    }
    if (newPassword !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    setLoading(true);
    try {
      const { confirmPasswordReset, signInWithEmailAndPassword } = await import('firebase/auth');
      await confirmPasswordReset(auth, oobCode, newPassword);

      const result = await signInWithEmailAndPassword(auth, email, newPassword);
      const idToken = await result.user.getIdToken();

      const res = await fetch(`${API_BASE_URL}/api/auth/reset-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ idToken, newPassword }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.message || 'Password reset failed');
        return;
      }

      localStorage.setItem('token', data.token);
      window.history.replaceState({}, '', '/');
      setStatus('done');
      onLogin(data.user);
    } catch (err) {
      setError(err.message || 'Password reset failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container">
      <div
        style={{
          position: 'fixed', inset: 0, display: 'flex',
          alignItems: 'center', justifyContent: 'center',
        }}
      >
        <div style={{ background: '#fff', borderRadius: 12, padding: 32, width: 360, boxShadow: '0 10px 40px rgba(0,0,0,0.15)' }}>
          <h1>Reset Password</h1>

          {status === 'verifying' && <p>Verifying link…</p>}

          {status === 'invalid' && (
            <p>This reset link is invalid or has expired. Please request a new one from the login page.</p>
          )}

          {status === 'ready' && (
            <form onSubmit={handleSubmit}>
              <p>Set a new password for {email}</p>
              {error && <p style={{ color: '#ff4d4f' }}>{error}</p>}
              <div className="input-box">
                <input
                  type="password"
                  placeholder="New Password (min 8 chars)"
                  required
                  minLength={8}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                />
                <i className="bx bxs-lock-alt"></i>
              </div>
              <div className="input-box">
                <input
                  type="password"
                  placeholder="Confirm Password"
                  required
                  minLength={8}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                />
                <i className="bx bxs-lock-alt"></i>
              </div>
              <button type="submit" className="btn" disabled={loading}>
                {loading ? 'Resetting…' : 'Reset Password'}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};

export default ResetPassword;
