import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import api, { errDetail } from "../services/api";
import { ErrorBox } from "../components/ui";

export default function ResetPassword() {
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const navigate = useNavigate();

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState(null);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.post("/api/auth/reset-password", {
        token,
        new_password: password,
      });
      setDone(true);
      setTimeout(() => navigate("/login", { replace: true }), 2500);
    } catch (err) {
      setError(errDetail(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen grid place-items-center px-4">
      <div className="card w-full max-w-sm">
        <h1 className="text-xl font-bold text-slate-900">Set a new password</h1>

        {!token ? (
          <div className="mt-6 space-y-4">
            <ErrorBox message="This reset link is malformed. Request a fresh one." />
            <Link
              to="/forgot-password"
              className="btn-primary w-full block text-center"
            >
              Request new link
            </Link>
          </div>
        ) : done ? (
          <p className="mt-6 text-sm text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg p-3">
            Password updated! Taking you to sign in…
          </p>
        ) : (
          <form onSubmit={submit} className="mt-6 space-y-4">
            <ErrorBox message={error} />
            <div>
              <label className="label">New password</label>
              <input
                className="input"
                type="password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              <p className="mt-1 text-xs text-slate-400">
                At least 8 characters with a letter and a digit.
              </p>
            </div>
            <div>
              <label className="label">Confirm new password</label>
              <input
                className="input"
                type="password"
                required
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
              />
            </div>
            <button className="btn-primary w-full" disabled={busy}>
              {busy ? "Saving…" : "Update password"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
