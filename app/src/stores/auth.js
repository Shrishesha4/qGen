import { writable } from 'svelte/store';

const storedToken = localStorage.getItem("token");
const storedUser = JSON.parse(localStorage.getItem("user") || "null");

export const authState = writable({
  token: storedToken || null,
  isAuthenticated: !!storedToken,
  user: storedUser
});

export function login(token, user) {
  localStorage.setItem("token", token);
  localStorage.setItem("user", JSON.stringify(user));
  authState.set({ token, isAuthenticated: true, user });
}

export function logout() {
  localStorage.removeItem("token");
  localStorage.removeItem("user");
  authState.set({ token: null, isAuthenticated: false, user: null });
}