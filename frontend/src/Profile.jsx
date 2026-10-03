import React, { useState } from 'react';
import { API_BASE_URL } from './config/api';
import { auth, changeAccountPassword } from './firebase';
import { checkPassword } from './authValidation';
import { authErrorMessage } from './authErrors';
import './Profile.css';
import AppNavbar from './AppNavbar';
import { FooterQuickLinks, FooterContactLinks, FooterCopyright } from './FooterParts';

const PasswordField = ({ id, label, icon, value, onChange, show, onToggle, placeholder, autoComplete, describedBy, children }) => (
  <div className="form-group">
    <label htmlFor={id}><i className={`bx ${icon}`}></i> {label}</label>
    <div className="password-input-wrap">
      <input
        id={id}
        type={show ? 'text' : 'password'}
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        autoComplete={autoComplete}
        aria-describedby={describedBy}
      />
      <button
        type="button"
        className="password-eye"
        onClick={onToggle}
        aria-label={show ? `Hide ${label.toLowerCase()}` : `Show ${label.toLowerCase()}`}
      >
        <i className={`bx ${show ? 'bx-hide' : 'bx-show'}`} aria-hidden="true"></i>
      </button>
    </div>
    {children}
  </div>
);

const CURRENT_PASSWORD_WRONG = ['auth/wrong-password', 'auth/invalid-credential', 'auth/invalid-login-credentials'];

const Profile = ({ user = {}, onUserUpdate, onBack, onNavigateToAbout, onNavigateToSettings, onNavigateToLibrary, onLogout, hasSearchedAuthor, onNavigateToExplorer }) => {
  const [fullName, setFullName] = useState(user.username || '');
  // The registered email is the account's identity and cannot be changed:
  // show the Firebase Authentication email (falling back to the profile copy).
  const email = auth?.currentUser?.email || user.email || '';
  const [designation, setDesignation] = useState(user.designation || '');
  const [isEditing, setIsEditing] = useState(false);
  const [profileMsg, setProfileMsg] = useState('');

  // Password change
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState({ current: false, next: false, confirm: false });
  const [passwordMsg, setPasswordMsg] = useState({ type: '', text: '' });
  const [changingPassword, setChangingPassword] = useState(false);
  const { rules: newPasswordRules, strong: newPasswordStrong } = checkPassword(newPassword);
  const toggleShow = (field) => setShowPassword((prev) => ({ ...prev, [field]: !prev[field] }));

  const token = localStorage.getItem('token');

  const handleSaveProfile = async (e) => {
    e.preventDefault();
    setProfileMsg('');
    try {
      const res = await fetch(`${API_BASE_URL}/api/auth/profile`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ username: fullName, designation }),
      });
      const data = await res.json();
      if (!res.ok) {
        setProfileMsg(data.message || 'Failed to update profile');
        return;
      }
      onUserUpdate({ username: data.username, designation: data.designation });
      setProfileMsg('Profile updated successfully!');
      setIsEditing(false);
    } catch {
      setProfileMsg('Network error. Is the server running?');
    }
  };

  const handlePasswordChange = async (e) => {
    e.preventDefault();
    const fail = (text) => setPasswordMsg({ type: 'error', text });
    setPasswordMsg({ type: '', text: '' });

    if (!currentPassword || !newPassword || !confirmPassword) return fail('Please fill in all password fields.');
    if (!newPasswordStrong) return fail('Your new password does not meet all the requirements.');
    if (newPassword !== confirmPassword) return fail('New password and confirmation do not match.');
    if (newPassword === currentPassword) return fail('Your new password must be different from your current password.');

    setChangingPassword(true);
    try {
      await changeAccountPassword(user.email, currentPassword, newPassword);
      setPasswordMsg({ type: 'success', text: 'Password changed successfully!' });
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      setShowPassword({ current: false, next: false, confirm: false });
    } catch (err) {
      if (CURRENT_PASSWORD_WRONG.includes(err.code)) {
        fail('Your current password is incorrect.');
      } else if (err.code === 'app/no-password-provider') {
        fail('This account signs in with Google and has no password yet. To set one, log out and use "Forgot Password?" on the login page.');
      } else {
        fail(authErrorMessage(err, 'Could not change your password. Please try again.'));
      }
    } finally {
      setChangingPassword(false);
    }
  };

  return (
    <div className="profile-container">
      <AppNavbar activePage="profile" onDashboard={onBack} onExplorer={onNavigateToExplorer} onLibrary={onNavigateToLibrary} onAbout={onNavigateToAbout} onProfile={() => {}} onLogout={onLogout} />

      {/* Main Content */}
      <main className="dashboard-main">
        <div className="welcome-section">
          <h2>Profile Settings</h2>
        </div>

        {/* Account Information Section */}
        <section className="section-box">
          <div className="section-header">
            <h2 className="section-title">Account Information</h2>
            <button className="edit-btn" onClick={() => { setIsEditing(!isEditing); setProfileMsg(''); }}>
              <i className='bx bx-edit-alt'></i>
              {isEditing ? 'Cancel' : 'Edit'}
            </button>
          </div>
          {profileMsg && (
            <p style={{ padding: '0 24px', color: profileMsg.includes('success') ? '#52c41a' : '#ff4d4f', fontWeight: 500 }}>
              {profileMsg}
            </p>
          )}
          <div className="section-content">
            {isEditing ? (
              <form className="account-form" onSubmit={handleSaveProfile}>
                <div className="form-row">
                  <div className="form-group">
                    <label><i className='bx bx-user'></i> Full Name</label>
                    <input type="text" value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="Enter your full name" required />
                  </div>
                  <div className="form-group">
                    <label htmlFor="profile-email"><i className='bx bx-envelope'></i> Email Address</label>
                    <input
                      id="profile-email"
                      type="email"
                      className="readonly-input"
                      value={email}
                      readOnly
                      tabIndex={-1}
                      aria-readonly="true"
                      aria-describedby="profile-email-note"
                    />
                    <small id="profile-email-note" className="readonly-note">Your registered email address cannot be changed.</small>
                  </div>
                </div>
                <div className="form-row">
                  <div className="form-group">
                    <label><i className='bx bx-briefcase'></i> Designation</label>
                    <input type="text" value={designation} onChange={(e) => setDesignation(e.target.value)} placeholder="Enter your designation" required />
                  </div>
                </div>
                <div className="form-actions">
                  <button type="submit" className="save-btn"><i className='bx bx-check'></i> Save Changes</button>
                  <button type="button" className="btn-secondary" onClick={() => setIsEditing(false)}><i className='bx bx-x'></i> Cancel</button>
                </div>
              </form>
            ) : (
              <div className="account-info">
                <div className="info-item">
                  <div className="info-label"><i className='bx bx-user'></i><span>Full Name</span></div>
                  <div className="info-value">{fullName}</div>
                </div>
                <div className="info-item">
                  <div className="info-label"><i className='bx bx-envelope'></i><span>Email Address</span></div>
                  <div className="info-value">{email}</div>
                </div>
                <div className="info-item">
                  <div className="info-label"><i className='bx bx-briefcase'></i><span>Designation</span></div>
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
          {passwordMsg.text && (
            <p
              style={{ padding: '0 24px', color: passwordMsg.type === 'success' ? '#52c41a' : '#ff4d4f', fontWeight: 500 }}
              role={passwordMsg.type === 'success' ? 'status' : 'alert'}
            >
              {passwordMsg.text}
            </p>
          )}
          <div className="section-content">
            <form className="password-form" onSubmit={handlePasswordChange} noValidate>
              <div className="form-row">
                <PasswordField
                  id="current-password"
                  label="Current Password"
                  icon="bx-lock-open"
                  placeholder="Enter current password"
                  autoComplete="current-password"
                  value={currentPassword}
                  onChange={setCurrentPassword}
                  show={showPassword.current}
                  onToggle={() => toggleShow('current')}
                />
              </div>
              <div className="form-row">
                <PasswordField
                  id="new-password"
                  label="New Password"
                  icon="bx-lock"
                  placeholder="Enter new password"
                  autoComplete="new-password"
                  describedBy="new-password-rules"
                  value={newPassword}
                  onChange={setNewPassword}
                  show={showPassword.next}
                  onToggle={() => toggleShow('next')}
                >
                  {newPassword && (
                    <ul id="new-password-rules" className="profile-password-rules">
                      {newPasswordRules.map((rule) => (
                        <li key={rule.id} className={rule.met ? 'met' : ''}>
                          <i className={`bx ${rule.met ? 'bx-check-circle' : 'bx-circle'}`} aria-hidden="true"></i>
                          {rule.label}
                        </li>
                      ))}
                    </ul>
                  )}
                </PasswordField>
                <PasswordField
                  id="confirm-new-password"
                  label="Confirm New Password"
                  icon="bx-lock-alt"
                  placeholder="Confirm new password"
                  autoComplete="new-password"
                  value={confirmPassword}
                  onChange={setConfirmPassword}
                  show={showPassword.confirm}
                  onToggle={() => toggleShow('confirm')}
                />
              </div>
              <div className="form-actions">
                <button type="submit" className="change-password-btn" disabled={changingPassword}>
                  <i className='bx bx-key'></i> {changingPassword ? 'Updating…' : 'Update Password'}
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
              <FooterQuickLinks />
            </ul>
          </div>
          <div className="footer-section">
            <h4>Contact</h4>
            <ul>
              <FooterContactLinks />
            </ul>
          </div>
        </div>
        <FooterCopyright />
      </footer>
    </div>
  );
};

export default Profile;
