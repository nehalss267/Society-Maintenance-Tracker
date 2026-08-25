import { useState } from "react";
import api, { errDetail } from "../services/api";
import { ErrorBox } from "../components/ui";

export default function Settings() {
  const [form, setForm] = useState({
    current_password: "",
    new_password: "",
    confirm: "",
  });
  const [error, setError] = useState(null);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    if (form.new_password !== form.confirm) {
      setError("New passwords do not match.");
      return;
    }
    if (form.new_password === form.current_password) {
      setError("New password must differ from the current one.");
      return;
    }
    setBusy(true);
    setError(null);
    setDone(false);
    try {
      await api.patch("/api/auth/change-password", {
        current_password: form.current_password,
        new_password: form.new_password,
      });
      setDone(true);
      setForm({ current_password: "", new_password: "", confirm: "" });
    } catch (err) {
      setError(errDetail(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="max-w-md">
      <h1 className="text-2xl font-bold text-slate-900 mb-6">Settings</h1>

      <div className="card">
        <h2 className="font-semibold text-slate-900">Change password</h2>
        <p className="mt-1 text-sm text-slate-500">
          Use at least 8 characters with a letter and a digit.
        </p>

        <form onSubmit={submit} className="mt-4 space-y-4">
          <ErrorBox message={error} />
          {done && (
            <p className="text-sm text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg p-3">
              Password changed.
            </p>
          )}
          <div>
            <label className="label">Current password</label>
            <input
              className="input"
              type="password"
              required
              value={form.current_password}
              onChange={set("current_password")}
            />
          </div>
          <div>
            <label className="label">New password</label>
            <input
              className="input"
              type="password"
              required
              minLength={8}
              value={form.new_password}
              onChange={set("new_password")}
            />
          </div>
          <div>
            <label className="label">Confirm new password</label>
            <input
              className="input"
              type="password"
              required
              value={form.confirm}
              onChange={set("confirm")}
            />
          </div>
          <button className="btn-primary" disabled={busy}>
            {busy ? "Saving…" : "Change password"}
          </button>
        </form>
      </div>
    </div>
  );
}
