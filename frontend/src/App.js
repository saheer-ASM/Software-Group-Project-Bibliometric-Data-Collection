import React, { useState } from 'react';
import AuthForm from './AuthForm';
import Dashboard from './Dashboard';
import DataExplorer from './DataExplorer';
import AboutUs from './AboutUs';
import Profile from './Profile';
import './App.css';

function App() {
  const [currentPage, setCurrentPage] = useState('login'); // 'login', 'dashboard', 'explorer', 'settings', 'about', 'profile'
  const [username, setUsername] = useState('');
  const [userEmail, setUserEmail] = useState('');
  const [authorName, setAuthorName] = useState('');
  const [hasSearchedAuthor, setHasSearchedAuthor] = useState(false);

  const handleLogin = (user) => {
    setUsername(user);
    setUserEmail(`${user.toLowerCase().replace(' ', '')}@university.edu`);
    setCurrentPage('dashboard');
  };

  const handleLogout = () => {
    setCurrentPage('login');
    setUsername('');
    setUserEmail('');
    setAuthorName('');
    setHasSearchedAuthor(false);
  };

  const handleNavigateToExplorer = (searchedAuthor) => {
    setAuthorName(searchedAuthor);
    setHasSearchedAuthor(true);
    setCurrentPage('explorer');
  };

  const handleResetSearch = () => {
    setAuthorName('');
    setHasSearchedAuthor(false);
  };

  const handleNavigateToSettings = (e) => {
    e.preventDefault();
    setCurrentPage('profile');
  };

  const handleNavigateToAbout = (e) => {
    e.preventDefault();
    setCurrentPage('about');
  };

  const handleNavigateToProfile = (e) => {
    e.preventDefault();
    setCurrentPage('profile');
  };

  const handleBackToDashboard = (e) => {
    if (e && e.preventDefault) {
      e.preventDefault();
    }
    setCurrentPage('dashboard');
  };

  return (
    <div className="App">
      {currentPage === 'login' && (
        <AuthForm onLogin={handleLogin} />
      )}
      {currentPage === 'dashboard' && (
        <Dashboard 
          username={username} 
          onLogout={handleLogout}
          onNavigateToExplorer={handleNavigateToExplorer}
          onNavigateToSettings={handleNavigateToSettings}
          onNavigateToAbout={handleNavigateToAbout}
          onNavigateToProfile={handleNavigateToProfile}
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
        />
      )}
      {currentPage === 'profile' && (
        <Profile 
          username={username}
          userEmail={userEmail}
          onBack={handleBackToDashboard}
          onNavigateToSettings={handleNavigateToSettings}
          onNavigateToAbout={handleNavigateToAbout}
          onLogout={handleLogout}
          hasSearchedAuthor={hasSearchedAuthor}
          onNavigateToExplorer={handleNavigateToExplorer}
        />
      )}
    </div>
  );
}

export default App;
