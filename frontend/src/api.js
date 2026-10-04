// Backend base URL: trailing slash stripped, localhost fallback when VITE_API_URL is unset at build time.
export const API = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/+$/, '')
