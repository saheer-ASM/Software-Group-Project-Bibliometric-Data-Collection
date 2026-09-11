import React, { useState } from 'react';
import AuthForm from './AuthForm';
import Dashboard from './Dashboard';
import DataExplorer from './DataExplorer';
import AboutUs from './AboutUs';
import Profile from './Profile';
import Library from './Library';
import './App.css';

function App() {
  const [currentPage, setCurrentPage] = useState('login');
  const [user, setUser] = useState(null); // { id, username, email, designation }
  const [authorName, setAuthorName] = useState('');
  const [hasSearchedAuthor, setHasSearchedAuthor] = useState(false);

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
      {currentPage === 'login' && (
        <AuthForm onLogin={handleLogin} />
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
    </div>
  );
}

export default App;
