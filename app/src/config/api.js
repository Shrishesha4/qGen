// API configuration
// In production (Docker), use relative URL since frontend is served by backend
// In development, use localhost:8000
const API_URL = import.meta.env.VITE_API_URL || 
  (import.meta.env.PROD ? '' : 'http://localhost:8000');

export { API_URL };
