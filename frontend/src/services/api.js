import axios from "axios";

// Dev: empty base so Vite's /api proxy handles it. Prod build: fall back to
// the deployed API if VITE_API_URL was missing/stale at build time.
const API_BASE =
  import.meta.env.VITE_API_URL ||
  (import.meta.env.DEV ? "" : "https://smt-api-w11c.onrender.com");

const api = axios.create({
  baseURL: API_BASE,
  // Render's free tier sleeps the API after ~15 min idle; waking can take
  // 50-75s, so allow enough headroom before giving up with an error.
  timeout: 90000,
});

api.interceptors.request.use((config) => {
  const raw = localStorage.getItem("smt_auth");
  if (raw) {
    try {
      const { token } = JSON.parse(raw);
      if (token) config.headers.Authorization = `Bearer ${token}`;
    } catch {
      /* corrupted storage - ignore */
    }
  }
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem("smt_auth");
      if (!window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
    }
    return Promise.reject(err);
  }
);

export function errDetail(e) {
  if (e.code === "ECONNABORTED") {
    return "The server took too long to respond (it may be waking up on the free tier). Please try again.";
  }

  return (
    e.response?.data?.detail ||
    (Array.isArray(e.response?.data?.detail)
      ? e.response.data.detail.map((d) => d.msg).join(", ")
      : null) ||
    e.message
  );
}

export default api;
