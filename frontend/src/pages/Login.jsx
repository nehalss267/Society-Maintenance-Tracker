import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { homeFor } from "../components/Protected";
import { ErrorBox } from "../components/ui";
import { errDetail } from "../services/api";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const user = await login(email, password);
      navigate(homeFor(user.role), { replace: true });
    } catch (err) {
      setError(errDetail(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen grid place-items-center px-4">
      <div className="card w-full max-w-sm">
        <h1 className="text-xl font-bold text-slate-900">Sign in</h1>
        <p className="mt-1 text-sm text-slate-500">
          Society Maintenance Tracker
        </p>

        <form onSubmit={submit} className="mt-6 space-y-4">
          <ErrorBox message={error} />
          <div>
            <label className="label">Email</label>
            <input
              className="input"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div>
            <label className="label">Password</label>
            <input
              className="input"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          <button className="btn-primary w-full" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <p className="mt-4 text-sm text-slate-500 text-center">
          New resident?{" "}
          <Link to="/register" className="text-indigo-600 font-medium">
            Create an account
          </Link>
        </p>
        <p className="mt-2 text-sm text-slate-500 text-center">
          <Link to="/forgot-password" className="text-indigo-600 font-medium">
            Forgot your password?
          </Link>
        </p>
      </div>
    </div>
  );
}
