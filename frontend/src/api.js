// Backend base URL: VITE_API_URL wins (trailing slash stripped). Unset: the hosted API in production builds, localhost in dev.
// The URL is public by nature (the browser calls it), so a built-in default is safe.
const HOSTED = 'https://forward-supply-api-sg.onrender.com'
export const API = (import.meta.env.VITE_API_URL || (import.meta.env.PROD ? HOSTED : 'http://localhost:8000')).replace(/\/+$/, '')
