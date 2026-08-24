import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export function RequireAuth({ children }) {
  const { auth, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen grid place-items-center text-slate-400 text-sm">
        Loading…
      </div>
    );
  }

  if (!auth) return <Navigate to="/login" replace />;

  return children;
}

export function RequireRoles({ roles, children }) {
  const { auth } = useAuth();

  if (!roles.includes(auth?.user?.role)) {
    return (
      <div className="card mt-8">
        <p className="text-sm text-rose-600 font-medium">403 - Access denied</p>
        <p className="mt-1 text-sm text-slate-500">
          Your role ({auth?.user?.role}) cannot view this page.
        </p>
      </div>
    );
  }

  return children;
}

export const homeFor = (role) =>
  role === "RESIDENT" ? "/" : role === "ACCOUNTANT" ? "/accounting-dash" : "/staff";
