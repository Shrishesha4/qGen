import { writable } from 'svelte/store';

function createThemeStore() {
  const { subscribe, set, update } = writable('light');

  // Check if we're in browser
  const isBrowser = typeof window !== 'undefined';
  
  if (!isBrowser) {
    return { subscribe, setTheme: () => {}, toggleTheme: () => {}, clearPreference: () => {} };
  }

  // Detect system preference
  const getSystemTheme = () => {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  };

  function applyTheme(theme) {
    const root = document.documentElement;
    if (theme === 'dark') {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }
  }

  // Initialize theme
  const savedTheme = localStorage.getItem('theme');
  const initialTheme = savedTheme || getSystemTheme();
  set(initialTheme);
  applyTheme(initialTheme);

  // Listen for system theme changes
  const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
  const handleSystemThemeChange = (e) => {
    // Only auto-switch if user hasn't set a manual preference
    if (!localStorage.getItem('theme')) {
      const newTheme = e.matches ? 'dark' : 'light';
      set(newTheme);
      applyTheme(newTheme);
    }
  };

  mediaQuery.addEventListener('change', handleSystemThemeChange);

  return {
    subscribe,
    setTheme: (theme) => {
      set(theme);
      applyTheme(theme);
      localStorage.setItem('theme', theme);
    },
    toggleTheme: () => {
      update(currentTheme => {
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        applyTheme(newTheme);
        localStorage.setItem('theme', newTheme);
        return newTheme;
      });
    },
    clearPreference: () => {
      localStorage.removeItem('theme');
      const systemTheme = getSystemTheme();
      set(systemTheme);
      applyTheme(systemTheme);
    }
  };
}

export const theme = createThemeStore();
