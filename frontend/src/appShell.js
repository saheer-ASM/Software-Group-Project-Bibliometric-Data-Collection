import { createContext, useContext } from 'react';

// App-wide actions shared by the navbar and every page footer, so links work
// the same everywhere without threading props through each page:
//   goTo('dashboard' | 'explorer' | 'settings' | 'about' | 'admin')
//   openSupport('feedback' | 'issue')
//   isAdmin: whether to SHOW admin navigation (access is enforced by Firestore rules)
export const AppShellContext = createContext({
  goTo: () => {},
  openSupport: () => {},
  isAdmin: false,
});

export const useAppShell = () => useContext(AppShellContext);
