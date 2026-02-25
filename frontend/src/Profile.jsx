import React, { useState } from 'react';
import './Profile.css';

const Profile = ({ username = "Jone Smith", userEmail = "researcher@university.edu", onBack, onNavigateToAbout, onNavigateToSettings, onLogout, hasSearchedAuthor, onNavigateToExplorer }) => {
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
    <div className="profile-container">
      {/* Header */}
      <header className="dashboard-header">
        <div className="header-left">
          <i className='bx bxs-graduation'></i>
          <h1 className="logo">ScholarMetrics</h1>
        </div>
        <div className="header-right">
          <nav className="header-nav">
            <a href="#dashboard" onClick={onBack} className="nav-link">Dashboard</a>
            {hasSearchedAuthor && (
              <a href="#explorer" className="nav-link" onClick={(e) => { e.preventDefault(); onNavigateToExplorer(''); }}>Data Explorer</a>
            )}
            <a href="#about" className="nav-link" onClick={onNavigateToAbout}>About Us</a>
            <button className="nav-link logout-btn" onClick={onLogout}>Logout</button>
          </nav>
          <div className="user-icon active">
            <i className='bx bxs-user-circle'></i>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="dashboard-main">
        {/* Welcome Section */}
        <div className="welcome-section">
          <h2>Profile Settings</h2>
        </div>

        {/* Profile Stats Cards */}
        <section className="profile-stats">
          <div className="stat-card profile-stat">
            <div className="stat-icon">
              <i className='bx bxs-user-circle'></i>
            </div>
            <div className="stat-info">
              <div className="stat-label">Full Name</div>
              <div className="stat-value">{fullName}</div>
            </div>
          </div>
          <div className="stat-card profile-stat">
            <div className="stat-icon">
              <i className='bx bxs-envelope'></i>
            </div>
            <div className="stat-info">
              <div className="stat-label">Email Address</div>
              <div className="stat-value">{email}</div>
            </div>
          </div>
          <div className="stat-card profile-stat">
            <div className="stat-icon">
              <i className='bx bxs-briefcase'></i>
            </div>
            <div className="stat-info">
              <div className="stat-label">Designation</div>
              <div className="stat-value">{designation}</div>
            </div>
          </div>
        </section>

        {/* Account Information Section */}
        <section className="section-box">
          <div className="section-header">
            <h2 className="section-title">Account Information</h2>
            <button className="edit-btn" onClick={handleEditToggle}>
              <i className='bx bx-edit-alt'></i>
              {isEditing ? 'Cancel' : 'Edit'}
            </button>
          </div>
          <div className="section-content">
            {isEditing ? (
              <form className="account-form" onSubmit={(e) => { e.preventDefault(); handleSaveProfile(); }}>
                <div className="form-row">
                  <div className="form-group">
                    <label><i className='bx bx-user'></i> Full Name</label>
                    <input
                      type="text"
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      placeholder="Enter your full name"
                      required
                    />
                  </div>
                  <div className="form-group">
                    <label><i className='bx bx-envelope'></i> Email Address</label>
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="Enter your email"
                      required
                    />
                  </div>
                </div>
                <div className="form-row">
                  <div className="form-group">
                    <label><i className='bx bx-briefcase'></i> Designation</label>
                    <input
                      type="text"
                      value={designation}
                      onChange={(e) => setDesignation(e.target.value)}
                      placeholder="Enter your designation"
                      required
                    />
                  </div>
                </div>
                <div className="form-actions">
                  <button type="submit" className="save-btn">
                    <i className='bx bx-check'></i>
                    Save Changes
                  </button>
                  <button type="button" className="btn-secondary" onClick={handleEditToggle}>
                    <i className='bx bx-x'></i>
                    Cancel
                  </button>
                </div>
              </form>
            ) : (
              <div className="account-info">
                <div className="info-item">
                  <div className="info-label">
                    <i className='bx bx-user'></i>
                    <span>Full Name</span>
                  </div>
                  <div className="info-value">{fullName}</div>
                </div>
                <div className="info-item">
                  <div className="info-label">
                    <i className='bx bx-envelope'></i>
                    <span>Email Address</span>
                  </div>
                  <div className="info-value">{email}</div>
                </div>
                <div className="info-item">
                  <div className="info-label">
                    <i className='bx bx-briefcase'></i>
                    <span>Designation</span>
                  </div>
                  <div className="info-value">{designation}</div>
                </div>
              </div>
            )}
          </div>
        </section>

        {/* Change Password Section */}
        <section className="section-box">
          <div className="section-header">
            <h2 className="section-title">Change Password</h2>
          </div>
          <div className="section-content">
            <form className="password-form" onSubmit={handlePasswordChange}>
              <div className="form-row">
                <div className="form-group">
                  <label><i className='bx bx-envelope'></i> Email Address</label>
                  <input
                    type="email"
                    placeholder="Enter your email"
                    value={emailAddress}
                    onChange={(e) => setEmailAddress(e.target.value)}
                    required
                  />
                </div>
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label><i className='bx bx-lock'></i> New Password</label>
                  <input
                    type="password"
                    placeholder="Enter new password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    minLength="8"
                  />
                </div>
                <div className="form-group">
                  <label><i className='bx bx-lock-alt'></i> Confirm Password</label>
                  <input
                    type="password"
                    placeholder="Confirm new password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    required
                    minLength="8"
                  />
                </div>
              </div>
              <div className="form-actions">
                <button type="submit" className="change-password-btn">
                  <i className='bx bx-key'></i>
                  Update Password
                </button>
              </div>
            </form>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="dashboard-footer">
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
              <li><a href="#dashboard" onClick={onBack}>Dashboard</a></li>
              <li><a href="#explorer">Data Explorer</a></li>
              <li><a href="#profile">Profile</a></li>
              <li><a href="#about" onClick={onNavigateToAbout}>About Us</a></li>
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

export default Profile;
