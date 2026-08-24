import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "",
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
  return (
    e.response?.data?.detail ||
    (Array.isArray(e.response?.data?.detail)
      ? e.response.data.detail.map((d) => d.msg).join(", ")
      : null) ||
    e.message
  );
}

export default api;
