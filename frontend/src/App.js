import React, { useEffect, useState } from 'react';
import AuthForm from './AuthForm';
import ResetPassword from './ResetPassword';
import Dashboard from './Dashboard';
import DataExplorer from './DataExplorer';
import AboutUs from './AboutUs';
import Profile from './Profile';
import Library from './Library';
import './App.css';
import { API_BASE_URL } from './config/api';
import { syncLibraryFromServer } from './services/researchLibrary';

function App() {
  const [currentPage, setCurrentPage] = useState(
    window.location.pathname === '/reset-password' ? 'reset-password' : 'login'
  );
  const [user, setUser] = useState(null); // { id, username, email, designation }
  const [authorName, setAuthorName] = useState('');
  const [hasSearchedAuthor, setHasSearchedAuthor] = useState(false);
  const [checkingSession, setCheckingSession] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (!token) {
      setCheckingSession(false);
      return;
    }
    fetch(`${API_BASE_URL}/api/auth/profile`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (response) => {
        if (!response.ok) throw new Error('Session expired');
        const profile = await response.json();
        setUser(profile);
        setCurrentPage('dashboard');
      })
      .catch(() => localStorage.removeItem('token'))
      .finally(() => setCheckingSession(false));
  }, []);

  useEffect(() => {
    if (user?.id) syncLibraryFromServer(user.id).catch(() => {});
  }, [user?.id]);

  const handleLogin = (userData) => {
    setUser(userData);
    setCurrentPage('dashboard');
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    setCurrentPage('login');
    setUser(null);
    setAuthorName('');
    setHasSearchedAuthor(false);
  };

  const handleUserUpdate = (updatedUser) => {
    setUser((prev) => ({ ...prev, ...updatedUser }));
  };

  const handleNavigateToExplorer = (searchedAuthor) => {
    const nextAuthor = typeof searchedAuthor === 'string' ? searchedAuthor.trim() : '';
    if (nextAuthor) {
      setAuthorName(nextAuthor);
      setHasSearchedAuthor(true);
    }
    setCurrentPage('explorer');
  };

  const handleResetSearch = () => {
    setAuthorName('');
    setHasSearchedAuthor(false);
  };

  const handleNavigateToSettings = (e) => {
    if (e && e.preventDefault) e.preventDefault();
    setCurrentPage('profile');
  };

  const handleNavigateToAbout = (e) => {
    if (e && e.preventDefault) e.preventDefault();
    setCurrentPage('about');
  };

  const handleNavigateToProfile = (e) => {
    if (e && e.preventDefault) e.preventDefault();
    setCurrentPage('profile');
  };

  const handleNavigateToLibrary = (e) => {
    if (e && e.preventDefault) e.preventDefault();
    setCurrentPage('library');
  };

  const handleBackToDashboard = (e) => {
    if (e && e.preventDefault) e.preventDefault();
    setCurrentPage('dashboard');
  };

  return (
    <div className="App">
      {checkingSession && <div className="app-session-loading" role="status">Restoring your session…</div>}
      {!checkingSession && <>
      {currentPage === 'login' && (
        <AuthForm onLogin={handleLogin} />
      )}
      {currentPage === 'reset-password' && (
        <ResetPassword onLogin={handleLogin} />
      )}
      {currentPage === 'dashboard' && (
        <Dashboard
          username={user?.username}
          onLogout={handleLogout}
          onNavigateToExplorer={handleNavigateToExplorer}
          onNavigateToSettings={handleNavigateToSettings}
          onNavigateToAbout={handleNavigateToAbout}
          onNavigateToProfile={handleNavigateToProfile}
          onNavigateToLibrary={handleNavigateToLibrary}
          hasSearchedAuthor={hasSearchedAuthor}
          onResetSearch={handleResetSearch}
        />
      )}
      {currentPage === 'explorer' && (
        <DataExplorer
          authorName={authorName}
          onBack={handleBackToDashboard}
          onNavigateToSettings={handleNavigateToSettings}
          onNavigateToAbout={handleNavigateToAbout}
          onNavigateToProfile={handleNavigateToProfile}
          onLogout={handleLogout}
          hasSearchedAuthor={hasSearchedAuthor}
          onResetSearch={handleResetSearch}
          onNavigateToExplorer={handleNavigateToExplorer}
          onNavigateToLibrary={handleNavigateToLibrary}
          user={user}
        />
      )}
      {currentPage === 'about' && (
        <AboutUs
          onBack={handleBackToDashboard}
          onNavigateToSettings={handleNavigateToSettings}
          onNavigateToProfile={handleNavigateToProfile}
          onLogout={handleLogout}
          hasSearchedAuthor={hasSearchedAuthor}
          onNavigateToExplorer={handleNavigateToExplorer}
          onNavigateToLibrary={handleNavigateToLibrary}
        />
      )}
      {currentPage === 'profile' && (
        <Profile
          user={user}
          onUserUpdate={handleUserUpdate}
          onBack={handleBackToDashboard}
          onNavigateToSettings={handleNavigateToSettings}
          onNavigateToAbout={handleNavigateToAbout}
          onLogout={handleLogout}
          hasSearchedAuthor={hasSearchedAuthor}
          onNavigateToExplorer={handleNavigateToExplorer}
          onNavigateToLibrary={handleNavigateToLibrary}
        />
      )}
      {currentPage === 'library' && (
        <Library
          user={user}
          onBack={handleBackToDashboard}
          onOpenAuthor={handleNavigateToExplorer}
          onNavigateToAbout={handleNavigateToAbout}
          onNavigateToProfile={handleNavigateToProfile}
          onLogout={handleLogout}
          hasSearchedAuthor={hasSearchedAuthor}
        />
      )}
      </>}
    </div>
  );
}

export default App;
