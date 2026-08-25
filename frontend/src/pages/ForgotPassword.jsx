import { useState } from "react";
import { Link } from "react-router-dom";
import { errDetail } from "../services/api";
import api from "../services/api";
import { ErrorBox } from "../components/ui";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.post("/api/auth/forgot-password", { email });
      setSent(true);
    } catch (err) {
      setError(errDetail(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen grid place-items-center px-4">
      <div className="card w-full max-w-sm">
        <h1 className="text-xl font-bold text-slate-900">Forgot password</h1>
        <p className="mt-1 text-sm text-slate-500">
          We'll email you a reset link valid for 30 minutes.
        </p>

        {sent ? (
          <div className="mt-6 space-y-4">
            <p className="text-sm text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg p-3">
              If that email is registered, a reset link is on its way. Check
              your inbox (and spam folder).
            </p>
            <Link to="/login" className="btn-secondary w-full block text-center">
              Back to sign in
            </Link>
          </div>
        ) : (
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
            <button className="btn-primary w-full" disabled={busy}>
              {busy ? "Sending…" : "Send reset link"}
            </button>
          </form>
        )}

        <p className="mt-4 text-sm text-slate-500 text-center">
          Remembered it?{" "}
          <Link to="/login" className="text-indigo-600 font-medium">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
