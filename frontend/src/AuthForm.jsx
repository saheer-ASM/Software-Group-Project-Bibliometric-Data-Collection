import React, { useState } from 'react';
import './AuthForm.css';

const AuthForm = ({ onLogin }) => {
  const [isActive, setIsActive] = useState(false);
  const [loginUsername, setLoginUsername] = useState('');
  const [registerUsername, setRegisterUsername] = useState('');
<<<<<<< HEAD
=======
  const [registerEmail, setRegisterEmail] = useState('');
  const [registerDesignation, setRegisterDesignation] = useState('');
  const [registerPassword, setRegisterPassword] = useState('');
  const [registerConfirmPassword, setRegisterConfirmPassword] = useState('');
>>>>>>> 3cd032d (Registration UI update)

  const handleRegisterClick = () => {
    setIsActive(true);
  };

  const handleLoginClick = () => {
    setIsActive(false);
  };

  const handleLoginSubmit = (e) => {
    e.preventDefault();
<<<<<<< HEAD
    // Pass username to parent component
    onLogin(loginUsername || 'User');
  };

  const handleRegisterSubmit = (e) => {
    e.preventDefault();
    // Pass username to parent component
    onLogin(registerUsername || 'User');
=======
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
>>>>>>> 3cd032d (Registration UI update)
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
            <i className='bx bxs-user'></i>
          </div>
          <div className="input-box">
            <input type="password" placeholder="Password" required />
            <i className='bx bxs-lock-alt'></i>
          </div>
          <div className="forgot-link">
            <a href="#">Forgot Password?</a>
          </div>
          <button type="submit" className="btn">Login</button>
          <p>or login with social platforms</p>
          <div className="social-icons">
            <a href="#"><i className='bx bxl-google'></i></a>
            <a href="#"><i className='bx bxl-facebook'></i></a>
            <a href="#"><i className='bx bxl-github'></i></a>
            <a href="#"><i className='bx bxl-linkedin'></i></a>
          </div>
        </form>
      </div>

      {/* Register Form */}
      <div className="form-box register">
        <form onSubmit={handleRegisterSubmit}>
          <h1>Registration</h1>
          <div className="input-box">
<<<<<<< HEAD
            <input 
              type="text" 
              placeholder="Username" 
              required 
=======
            <input
              type="text"
              placeholder="Full Name"
              required
>>>>>>> 3cd032d (Registration UI update)
              value={registerUsername}
              onChange={(e) => setRegisterUsername(e.target.value)}
            />
            <i className='bx bxs-user'></i>
          </div>
          <div className="input-box">
            <input type="email" placeholder="Email" required />
            <i className='bx bxs-envelope'></i>
          </div>
          <div className="input-box">
            <input type="text" placeholder="Designation" required />
            <i className='bx bxs-briefcase'></i>
          </div>
          <div className="input-box">
            <input type="password" placeholder="Password" required />
            <i className='bx bxs-lock-alt'></i>
          </div>
<<<<<<< HEAD
          <button type="submit" className="btn">Register</button>
=======
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
>>>>>>> 3cd032d (Registration UI update)
          <p>or register with social platforms</p>
          <div className="social-icons">
            <a href="#"><i className='bx bxl-google'></i></a>
            <a href="#"><i className='bx bxl-facebook'></i></a>
            <a href="#"><i className='bx bxl-github'></i></a>
            <a href="#"><i className='bx bxl-linkedin'></i></a>
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
