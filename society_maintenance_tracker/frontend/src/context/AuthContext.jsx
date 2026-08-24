import { createContext, useContext, useEffect, useState } from "react";
import api from "../services/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [auth, setAuth] = useState(() => {
    const raw = localStorage.getItem("smt_auth");
    return raw ? JSON.parse(raw) : null;
  });
  const [loading, setLoading] = useState(Boolean(auth));

  useEffect(() => {
    if (!auth) {
      setLoading(false);
      return;
    }
    api
      .get("/api/auth/me")
      .then((r) =>
        setAuth((prev) => {
          const next = { ...prev, user: r.data };
          localStorage.setItem("smt_auth", JSON.stringify(next));
          return next;
        })
      )
      .catch(() => setAuth(null))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const login = async (email, password) => {
    const r = await api.post("/api/auth/login", { email, password });
    const next = { token: r.data.access_token, user: null };
    localStorage.setItem("smt_auth", JSON.stringify(next));
    const me = await api.get("/api/auth/me");
    next.user = me.data;
    localStorage.setItem("smt_auth", JSON.stringify(next));
    setAuth(next);
    return me.data;
  };

  const register = async (name, email, password) => {
    await api.post("/api/auth/register", { name, email, password });
    return login(email, password);
  };

  const logout = () => {
    localStorage.removeItem("smt_auth");
    setAuth(null);
  };

  return (
    <AuthContext.Provider value={{ auth, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
