import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Navigate, Route, Routes, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import AuthForm from './AuthForm';
import ResetPassword from './ResetPassword';
import VerifyEmail from './VerifyEmail';
import Dashboard from './Dashboard';
import DataExplorer from './DataExplorer';
import AboutUs from './AboutUs';
import Profile from './Profile';
import Library from './Library';
import AdminDashboard from './AdminDashboard';
import SupportDialogs from './SupportDialogs';
import { AppShellContext } from './appShell';
import './App.css';
import { onIdTokenChanged, signOut } from 'firebase/auth';
import { auth, hasAdminClaim } from './firebase';
import { API_BASE_URL } from './config/api';
import { syncLibraryFromServer } from './services/researchLibrary';

// URL for each in-app page. The page components are unchanged; they still get
// their navigation callbacks as props, which now change the URL.
export const PATHS = {
  login: '/login',
  register: '/register',
  forgotPassword: '/forgot-password',
  verifyEmail: '/verify-email',
  resetPassword: '/reset-password',
  dashboard: '/dashboard',
  explorer: '/data-explorer',
  settings: '/settings', // the Profile Settings page
  about: '/about',
  library: '/library',
  admin: '/admin',
};

const SessionLoading = () => (
  <div className="app-session-loading" role="status">Restoring your session…</div>
);

// Pages that need a signed-in user. Signed-out visitors go to /login and come
// back to the page they asked for after logging in.
const RequireAuth = ({ user, rememberPage, children }) => {
  const location = useLocation();
  if (!user) {
    const state = rememberPage ? { from: location.pathname + location.search } : undefined;
    return <Navigate to={PATHS.login} replace state={state} />;
  }
  return children;
};

// Where to go after logging in: the protected page that sent the user to
// /login (RequireAuth stores it), otherwise the Dashboard.
const afterLoginPath = (location) => {
  const from = location.state?.from;
  return from && !from.startsWith(PATHS.login) ? from : PATHS.dashboard;
};

// Login/register/forgot-password are for signed-out visitors only.
const GuestOnly = ({ user, children }) => {
  const location = useLocation();
  return user ? <Navigate to={afterLoginPath(location)} replace /> : children;
};

function App() {
  const location = useLocation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [user, setUser] = useState(null); // { id, username, email, designation }
  const [authorName, setAuthorName] = useState('');
  const [hasSearchedAuthor, setHasSearchedAuthor] = useState(false);
  const [checkingSession, setCheckingSession] = useState(true);
  const [supportDialog, setSupportDialog] = useState(null); // 'feedback' | 'issue' | null
  const [isAdmin, setIsAdmin] = useState(false);
  const [adminChecked, setAdminChecked] = useState(false);
  // True while the user is logging out on purpose, so /login does not offer to
  // return them (or the next person) to the page they left.
  const loggingOut = useRef(false);

  // Admin navigation is shown only when the Firebase ID token carries the
  // 'admin' custom claim. Firestore Security Rules enforce the same claim, so
  // this flag never grants access by itself.
  useEffect(() => {
    if (!auth) {
      setAdminChecked(true);
      return undefined;
    }
    return onIdTokenChanged(auth, (firebaseUser) => {
      hasAdminClaim(firebaseUser)
        .then(setIsAdmin)
        .catch(() => setIsAdmin(false))
        .finally(() => setAdminChecked(true));
    });
  }, []);

  useEffect(() => {
    window.scrollTo(0, 0);
    if (location.pathname === PATHS.login) loggingOut.current = false;
  }, [location.pathname]);

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
        setUser(await response.json());
      })
      .catch(() => localStorage.removeItem('token'))
      .finally(() => setCheckingSession(false));
  }, []);

  useEffect(() => {
    if (user?.id) syncLibraryFromServer(user.id).catch(() => {});
  }, [user?.id]);

  // /data-explorer?author=Name opens that author's profile (also after a refresh
  // or from a bookmarked link).
  const urlAuthor = location.pathname === PATHS.explorer ? (searchParams.get('author') || '').trim() : '';
  useEffect(() => {
    if (urlAuthor && urlAuthor !== authorName) {
      setAuthorName(urlAuthor);
      setHasSearchedAuthor(true);
    }
  }, [urlAuthor]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleAuthNavigate = useCallback((path, state) => {
    navigate(path, state ? { state } : undefined);
  }, [navigate]);

  // After login, return to the page that sent the user to /login, else Dashboard.
  const handleLogin = (userData) => {
    loggingOut.current = false;
    setUser(userData);
    navigate(afterLoginPath(location), { replace: true });
  };

  const handleLogout = () => {
    loggingOut.current = true;
    localStorage.removeItem('token');
    // End the Firebase session too, so the next person on this browser can't
    // reuse it (e.g. to link sign-in methods).
    if (auth) signOut(auth).catch(() => {});
    setUser(null);
    setAuthorName('');
    setHasSearchedAuthor(false);
    navigate(PATHS.login);
  };

  const handleUserUpdate = (updatedUser) => {
    setUser((prev) => ({ ...prev, ...updatedUser }));
  };

  const go = (path) => (e) => {
    if (e && e.preventDefault) e.preventDefault();
    navigate(path);
  };

  const handleNavigateToExplorer = (searchedAuthor) => {
    const nextAuthor = typeof searchedAuthor === 'string' ? searchedAuthor.trim() : '';
    if (nextAuthor) {
      setAuthorName(nextAuthor);
      setHasSearchedAuthor(true);
    }
    const author = nextAuthor || authorName;
    navigate(author ? `${PATHS.explorer}?author=${encodeURIComponent(author)}` : PATHS.explorer);
  };

  const handleResetSearch = () => {
    setAuthorName('');
    setHasSearchedAuthor(false);
    if (location.pathname === PATHS.explorer && searchParams.get('author')) {
      navigate(PATHS.explorer, { replace: true });
    }
  };

  const handleNavigateToSettings = go(PATHS.settings);
  const handleNavigateToAbout = go(PATHS.about);
  const handleNavigateToProfile = go(PATHS.settings);
  const handleNavigateToLibrary = go(PATHS.library);
  const handleBackToDashboard = go(PATHS.dashboard);

  // Shared by the navbar and every page footer (see appShell.js).
  const appShell = useMemo(() => ({
    isAdmin,
    paths: PATHS,
    goTo: (page) => {
      if (page === 'explorer') handleNavigateToExplorer('');
      else navigate(PATHS[page] || PATHS.dashboard);
    },
    openSupport: (kind) => setSupportDialog(kind),
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }), [isAdmin, navigate, authorName]);

  // Feedback/issue modal opened without a Firebase session: back to login.
  const handleSupportLoginRequired = () => {
    setSupportDialog(null);
    handleLogout();
  };

  const loginNotice = location.state?.notice
    || (searchParams.get('verified') === '1' ? 'Your email has been verified. You can now log in.' : '');

  const authForm = (mode) => (
    <GuestOnly user={user}>
      <AuthForm mode={mode} onLogin={handleLogin} onNavigate={handleAuthNavigate} notice={mode === 'login' ? loginNotice : ''} />
    </GuestOnly>
  );

  const protectedPage = (element) => (
    <RequireAuth user={user} rememberPage={!loggingOut.current}>{element}</RequireAuth>
  );

  return (
    <AppShellContext.Provider value={appShell}>
    <div className="App">
      {checkingSession ? <SessionLoading /> : (
        <Routes>
          {/* Signed-out pages */}
          <Route path={PATHS.login} element={authForm('login')} />
          <Route path={PATHS.register} element={authForm('register')} />
          <Route path={PATHS.forgotPassword} element={authForm('forgot')} />
          <Route
            path={PATHS.verifyEmail}
            element={(
              <GuestOnly user={user}>
                <VerifyEmail
                  key={location.key}
                  onNavigate={handleAuthNavigate}
                  initialNotice={location.state?.notice || ''}
                  initialError={location.state?.error || ''}
                />
              </GuestOnly>
            )}
          />
          {/* Firebase email-action links; works signed in or out. */}
          <Route path={PATHS.resetPassword} element={<ResetPassword onLogin={handleLogin} onNavigate={handleAuthNavigate} />} />

          {/* Signed-in pages */}
          <Route
            path={PATHS.dashboard}
            element={protectedPage(
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
              />,
            )}
          />
          <Route
            path={PATHS.explorer}
            element={protectedPage(
              <DataExplorer
                authorName={urlAuthor || authorName}
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
              />,
            )}
          />
          <Route
            path={PATHS.about}
            element={protectedPage(
              <AboutUs
                onBack={handleBackToDashboard}
                onNavigateToSettings={handleNavigateToSettings}
                onNavigateToProfile={handleNavigateToProfile}
                onLogout={handleLogout}
                hasSearchedAuthor={hasSearchedAuthor}
                onNavigateToExplorer={handleNavigateToExplorer}
                onNavigateToLibrary={handleNavigateToLibrary}
              />,
            )}
          />
          <Route
            path={PATHS.settings}
            element={protectedPage(
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
              />,
            )}
          />
          <Route
            path={PATHS.library}
            element={protectedPage(
              <Library
                user={user}
                onBack={handleBackToDashboard}
                onOpenAuthor={handleNavigateToExplorer}
                onNavigateToAbout={handleNavigateToAbout}
                onNavigateToProfile={handleNavigateToProfile}
                onLogout={handleLogout}
                hasSearchedAuthor={hasSearchedAuthor}
              />,
            )}
          />
          <Route
            path={PATHS.admin}
            element={protectedPage(
              !adminChecked ? <SessionLoading /> : isAdmin ? (
                <AdminDashboard
                  onBack={handleBackToDashboard}
                  onNavigateToExplorer={handleNavigateToExplorer}
                  onNavigateToLibrary={handleNavigateToLibrary}
                  onNavigateToAbout={handleNavigateToAbout}
                  onNavigateToProfile={handleNavigateToProfile}
                  onLogout={handleLogout}
                />
              ) : <Navigate to={PATHS.dashboard} replace />,
            )}
          />

          {/* Old/alias URLs and everything else */}
          <Route path="/profile" element={<Navigate to={PATHS.settings} replace />} />
          <Route path="/explorer" element={<Navigate to={PATHS.explorer} replace />} />
          <Route path="*" element={<Navigate to={user ? PATHS.dashboard : PATHS.login} replace />} />
        </Routes>
      )}
      <SupportDialogs
        kind={supportDialog}
        onClose={() => setSupportDialog(null)}
        onRequireLogin={handleSupportLoginRequired}
      />
    </div>
    </AppShellContext.Provider>
  );
}

export default App;
