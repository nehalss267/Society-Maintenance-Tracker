import { useEffect, useState } from "react";
import api, { errDetail } from "../services/api";
import { useAuth } from "../context/AuthContext";
import { Empty, ErrorBox } from "../components/ui";

const STAFF = ["COMMITTEE", "ADMIN"];

export default function Notices() {
  const { auth } = useAuth();
  const canManage = STAFF.includes(auth.user.role);

  const [notices, setNotices] = useState([]);
  const [error, setError] = useState(null);
  const [form, setForm] = useState({ title: "", content: "", is_important: false });
  const [busy, setBusy] = useState(false);

  const load = () =>
    api
      .get("/api/notices")
      .then((r) => setNotices(r.data.items || r.data))
      .catch((e) => setError(errDetail(e)));

  useEffect(load, []);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.post("/api/admin/notices", form);
      setForm({ title: "", content: "", is_important: false });
      load();
    } catch (err) {
      setError(errDetail(err));
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id) => {
    if (!confirm("Delete this notice?")) return;
    try {
      await api.delete(`/api/admin/notices/${id}`);
      load();
    } catch (err) {
      alert(errDetail(err));
    }
  };

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-900 mb-6">Notices</h1>
      <ErrorBox message={error} />

      {canManage && (
        <form onSubmit={submit} className="card mb-6 space-y-3">
          <input
            className="input"
            placeholder="Title"
            required
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
          />
          <textarea
            className="input"
            rows={3}
            placeholder="Content"
            required
            value={form.content}
            onChange={(e) => setForm({ ...form, content: e.target.value })}
          />
          <div className="flex items-center justify-between">
            <label className="flex items-center gap-2 text-sm text-slate-600">
              <input
                type="checkbox"
                checked={form.is_important}
                onChange={(e) => setForm({ ...form, is_important: e.target.checked })}
              />
              Important (pins + emails residents)
            </label>
            <button className="btn-primary" disabled={busy}>
              {busy ? "Posting…" : "Post notice"}
            </button>
          </div>
        </form>
      )}

      {notices.length === 0 ? (
        <Empty>No notices yet.</Empty>
      ) : (
        <div className="space-y-3">
          {notices.map((n) => (
            <div
              key={n.id}
              className={`card ${n.is_important ? "border-l-4 border-l-indigo-500" : ""}`}
            >
              <div className="flex items-start justify-between">
                <div>
                  <p className="font-semibold text-slate-900">
                    {n.is_important ? "📌 " : ""}{n.title}
                  </p>
                  <p className="mt-1 text-sm text-slate-600 whitespace-pre-wrap">
                    {n.content}
                  </p>
                  <p className="mt-2 text-xs text-slate-400">
                    {new Date(n.created_at).toLocaleString()}
                  </p>
                </div>
                {canManage && (
                  <button
                    className="text-xs text-rose-500 hover:text-rose-700"
                    onClick={() => remove(n.id)}
                  >
                    Delete
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
