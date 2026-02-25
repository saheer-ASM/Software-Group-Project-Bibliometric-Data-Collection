import React, { useState } from 'react';
import './Settings.css';

const Settings = ({ username = "Jone Smith", userEmail = "researcher@university.edu", onBack, onNavigateToAbout, onNavigateToProfile, onLogout }) => {
  const [fullName, setFullName] = useState(username);
  const [email, setEmail] = useState(userEmail);
  const [designation, setDesignation] = useState("Prof");
  const [isEditing, setIsEditing] = useState(false);

  // Password change states
  const [emailAddress, setEmailAddress] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  const handleEditToggle = () => {
    setIsEditing(!isEditing);
  };

  const handleSaveProfile = () => {
    // Add save logic here
    console.log('Profile saved:', { fullName, email, designation });
    setIsEditing(false);
  };

  const handlePasswordChange = (e) => {
    e.preventDefault();
    if (password !== confirmPassword) {
      alert('Passwords do not match!');
      return;
    }
    // Add password change logic here
    console.log('Password changed for:', emailAddress);
    alert('Password changed successfully!');
    setEmailAddress('');
    setPassword('');
    setConfirmPassword('');
  };

  return (
    <div className="settings-container">
      {/* Header */}
      <header className="settings-header">
        <div className="header-left">
          <i className='bx bxs-graduation'></i>
          <h1 className="logo">ScholarMetrics</h1>
        </div>
        <div className="header-right">
          <nav className="header-nav">
            <a href="#dashboard" onClick={onBack} className="nav-link">Dashboard</a>
            <a href="#settings" className="nav-link active">Settings</a>
            <a href="#about" className="nav-link" onClick={onNavigateToAbout}>About Us</a>
            <a href="#logout" className="nav-link" onClick={onLogout}>Logout</a>
          </nav>
          <div className="user-icon" onClick={onNavigateToProfile}>
            <i className='bx bxs-user-circle'></i>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="settings-main">
        {/* Account Information Section */}
        <section className="account-section">
          <div className="account-card">
            <h2 className="section-title">Account information</h2>
            {isEditing ? (
              <div className="account-form">
                <div className="form-group">
                  <label>Full Name:</label>
                  <input
                    type="text"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                  />
                </div>
                <div className="form-group">
                  <label>Email:</label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                  />
                </div>
                <div className="form-group">
                  <label>Designation:</label>
                  <input
                    type="text"
                    value={designation}
                    onChange={(e) => setDesignation(e.target.value)}
                  />
                </div>
                <button className="save-btn" onClick={handleSaveProfile}>
                  Save Changes
                </button>
              </div>
            ) : (
              <div className="account-info">
                <p><strong>Full Name :</strong> {fullName}</p>
                <p><strong>Email :</strong> {email}</p>
                <p><strong>Designation:</strong> {designation}</p>
              </div>
            )}
          </div>
          <div className="profile-picture-section">
            <div className="profile-picture">
              <i className='bx bxs-user'></i>
            </div>
            <button className="edit-btn" onClick={handleEditToggle}>
              {isEditing ? 'CANCEL' : 'EDIT'} <i className='bx bx-edit'></i>
            </button>
          </div>
        </section>

        {/* Change Password Section */}
        <section className="password-section">
          <div className="password-card">
            <h2 className="section-title-dark">Change Password</h2>
            <form onSubmit={handlePasswordChange}>
              <div className="input-group">
                <label>Email address</label>
                <input
                  type="email"
                  placeholder="Email address"
                  value={emailAddress}
                  onChange={(e) => setEmailAddress(e.target.value)}
                  required
                />
              </div>
              <div className="input-group">
                <label>Password</label>
                <input
                  type="password"
                  placeholder="Password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
              </div>
              <div className="input-group">
                <label>Confirm Password</label>
                <input
                  type="password"
                  placeholder="Confirm Password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                />
              </div>
              <button type="submit" className="change-password-btn">
                Change Password
              </button>
            </form>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="settings-footer">
        <div className="footer-content">
          <div className="footer-section">
            <div className="footer-title">
              <i className='bx bx-file'></i>
              <h3>ScholarMetrics</h3>
            </div>
            <p>Revolutionizing research evaluation through intelligent automation and comprehensive data collection across global scholarly databases.</p>
          </div>

          <div className="footer-section">
            <h4>Quick Links</h4>
            <ul>
              <li><a href="#dashboard">Dashboard</a></li>
              <li><a href="#explorer">Data Explorer</a></li>
              <li><a href="#settings">Settings</a></li>
              <li><a href="#about">About Us</a></li>
            </ul>
          </div>

          <div className="footer-section">
            <h4>Resources</h4>
            <ul>
              <li><a href="#docs">Documentation</a></li>
              <li><a href="#api">API Reference</a></li>
              <li><a href="#tutorials">Tutorials</a></li>
              <li><a href="#faq">FAQ</a></li>
            </ul>
          </div>

          <div className="footer-section">
            <h4>Contact</h4>
            <ul>
              <li><a href="#support">Support Center</a></li>
              <li><a href="mailto:info@academine.edu">info@academine.edu</a></li>
              <li><a href="#feedback">Send Feedback</a></li>
              <li><a href="#report">Report an Issue</a></li>
            </ul>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default Settings;
