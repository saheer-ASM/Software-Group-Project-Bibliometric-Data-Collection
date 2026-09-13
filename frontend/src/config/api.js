// In development, an empty base URL uses Create React App's proxy from
// localhost:3000 to the backend configured in package.json.
export const API_BASE_URL = (process.env.REACT_APP_API_URL || '').replace(/\/$/, '');
