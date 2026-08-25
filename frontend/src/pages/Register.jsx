import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { ErrorBox } from "../components/ui";
import { errDetail } from "../services/api";

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await register(form.name, form.email, form.password);
      navigate("/dashboard", { replace: true });
    } catch (err) {
      setError(errDetail(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen grid place-items-center px-4">
      <div className="card w-full max-w-sm">
        <h1 className="text-xl font-bold text-slate-900">Create account</h1>
        <p className="mt-1 text-sm text-slate-500">
          Resident registration - staff accounts are provisioned by an admin.
        </p>

        <form onSubmit={submit} className="mt-6 space-y-4">
          <ErrorBox message={error} />
          <div>
            <label className="label">Full name</label>
            <input className="input" required value={form.name} onChange={set("name")} />
          </div>
          <div>
            <label className="label">Email</label>
            <input
              className="input"
              type="email"
              required
              value={form.email}
              onChange={set("email")}
            />
          </div>
          <div>
            <label className="label">Password</label>
            <input
              className="input"
              type="password"
              required
              minLength={8}
              value={form.password}
              onChange={set("password")}
            />
          </div>
          <button className="btn-primary w-full" disabled={busy}>
            {busy ? "Creating…" : "Register"}
          </button>
        </form>

        <p className="mt-4 text-sm text-slate-500 text-center">
          Already registered?{" "}
          <Link to="/login" className="text-indigo-600 font-medium">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
