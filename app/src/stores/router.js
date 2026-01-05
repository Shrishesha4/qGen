import { writable } from 'svelte/store';
import { authState } from './auth.js';

// Initialize with current path, but we'll check auth later
const initialPath = window.location.pathname;
export const route = writable(initialPath);

export function navigate(path, { replace = false, state = {} } = {}) {
  if (replace) {
    window.history.replaceState(state, "", path);
  } else {
    window.history.pushState(state, "", path);
  }
  route.set(path);
}

window.onpopstate = () => {
  route.set(window.location.pathname);
};

// Check authentication and redirect if needed
authState.subscribe((auth) => {
  const currentPath = window.location.pathname;

  // If not authenticated and not on login page, redirect to login
  if (!auth.token && currentPath !== '/login') {
    navigate('/login', { replace: true });
  }
  // If authenticated and on login page, redirect to dashboard
  else if (auth.token && currentPath === '/login') {
    navigate('/dashboard', { replace: true });
  }
});
