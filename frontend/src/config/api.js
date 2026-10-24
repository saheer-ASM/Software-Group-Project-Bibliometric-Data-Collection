// In development, an empty base URL uses Create React App's proxy from
// localhost:3000 to the backend configured in package.json.
export const API_BASE_URL = (process.env.REACT_APP_API_URL || '').replace(/\/$/, '');

// The session header for signed-in API routes (search, compare, author
// suggestions, library). Empty when signed out; the backend then answers 401.
export const authHeaders = () => {
  const token = localStorage.getItem('token');
  return token ? { Authorization: `Bearer ${token}` } : {};
};
