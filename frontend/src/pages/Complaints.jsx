import { useEffect, useState } from "react";
import api, { errDetail } from "../services/api";
import { useAuth } from "../context/AuthContext";
import { Badge, Empty, ErrorBox } from "../components/ui";

const CATEGORIES = ["PLUMBING", "ELECTRICAL", "CLEANING", "SECURITY", "OTHER"];
const PRIORITIES = ["LOW", "MEDIUM", "HIGH", "URGENT"];
const STAFF = ["COMMITTEE", "ACCOUNTANT", "ADMIN"];

export default function Complaints() {
  const { auth } = useAuth();
  const isStaff = STAFF.includes(auth.user.role);

  const [complaints, setComplaints] = useState([]);
  const [error, setError] = useState(null);
  const [detail, setDetail] = useState(null);

  const [form, setForm] = useState({ category: "PLUMBING", description: "" });
  const [photo, setPhoto] = useState(null);
  const [creating, setCreating] = useState(false);

  const [filters, setFilters] = useState({ status: "", priority: "", overdue: false });

  const load = () => {
    const params = {};
    if (filters.status) params.status = filters.status;
    if (filters.priority) params.priority = filters.priority;
    if (filters.overdue) params.overdue = true;

    const url = isStaff ? "/api/admin/complaints" : "/api/complaints";
    api
      .get(url, { params })
      .then((r) => {
        const d = r.data;
        setComplaints(Array.isArray(d) ? d : d.items || []);
      })
      .catch((e) => setError(errDetail(e)));
  };

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(load, [filters, isStaff]);

  const submit = async (e) => {
    e.preventDefault();
    setCreating(true);
    setError(null);
    try {
      const fd = new FormData();
      fd.append("category", form.category);
      fd.append("description", form.description);
      if (photo) fd.append("photo", photo);
      await api.post("/api/complaints", fd);
      setForm({ category: "PLUMBING", description: "" });
      setPhoto(null);
      load();
    } catch (err) {
      setError(errDetail(err));
    } finally {
      setCreating(false);
    }
  };

  const openDetail = async (id) => {
    try {
      const url = isStaff ? `/api/admin/complaints/${id}` : `/api/complaints/${id}`;
      const r = await api.get(url);
      setDetail(r.data);
    } catch (err) {
      setError(errDetail(err));
    }
  };

  const patchStatus = async (id, status, note) => {
    try {
      await api.patch(`/api/admin/complaints/${id}/status`, { status, note });
      setDetail(null);
      load();
    } catch (err) {
      alert(errDetail(err));
    }
  };

  const patchPriority = async (id, priority) => {
    try {
      await api.patch(`/api/admin/complaints/${id}/priority`, { priority });
      load();
    } catch (err) {
      alert(errDetail(err));
    }
  };

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-900 mb-6">Complaints</h1>
      <ErrorBox message={error} />

      {!isStaff && (
        <form onSubmit={submit} className="card mb-6 space-y-3">
          <h2 className="font-semibold text-slate-900">New complaint</h2>
          <div className="flex gap-3">
            <select
              className="input w-44"
              value={form.category}
              onChange={(e) => setForm({ ...form, category: e.target.value })}
            >
              {CATEGORIES.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
            <input
              className="input"
              placeholder="Describe the issue…"
              required
              minLength={10}
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={(e) => setPhoto(e.target.files[0] || null)}
              className="text-sm"
            />
            <button className="btn-primary" disabled={creating}>
              {creating ? "Submitting…" : "Submit"}
            </button>
          </div>
        </form>
      )}

      {isStaff && (
        <div className="flex gap-2 mb-4">
          <select
            className="input w-40"
            value={filters.status}
            onChange={(e) => setFilters({ ...filters, status: e.target.value })}
          >
            <option value="">All statuses</option>
            <option>OPEN</option>
            <option>IN_PROGRESS</option>
            <option>RESOLVED</option>
          </select>
          <select
            className="input w-40"
            value={filters.priority}
            onChange={(e) => setFilters({ ...filters, priority: e.target.value })}
          >
            <option value="">All priorities</option>
            {PRIORITIES.map((p) => (
              <option key={p}>{p}</option>
            ))}
          </select>
          <label className="btn-secondary cursor-pointer">
            <input
              type="checkbox"
              className="mr-2"
              checked={filters.overdue}
              onChange={(e) => setFilters({ ...filters, overdue: e.target.checked })}
            />
            Overdue only
          </label>
        </div>
      )}

      {complaints.length === 0 ? (
        <Empty>No complaints found.</Empty>
      ) : (
        <table className="w-full bg-white rounded-xl border border-slate-200 overflow-hidden">
          <thead className="bg-slate-50">
            <tr>
              <th className="th">Category</th>
              <th className="th">Description</th>
              <th className="th">Status</th>
              <th className="th">Priority</th>
              {isStaff && <th className="th">Resident</th>}
              <th className="th"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {complaints.map((c) => (
              <tr key={c.id} className="hover:bg-slate-50">
                <td className="td font-medium">{c.category}</td>
                <td className="td max-w-xs truncate">{c.description}</td>
                <td className="td"><Badge value={c.status} /></td>
                <td className="td"><Badge value={c.priority} /></td>
                {isStaff && (
                  <td className="td">
                    {c.resident_name || c.resident_email}
                    {c.sla_overdue ? (
                      <span className="ml-2 text-xs text-rose-600 font-semibold">SLA!</span>
                    ) : null}
                  </td>
                )}
                <td className="td">
                  <button className="text-indigo-600 text-sm" onClick={() => openDetail(c.id)}>
                    View
                  </button>
                  {isStaff && c.status !== "RESOLVED" && (
                    <select
                      className="ml-3 text-xs border rounded px-1 py-0.5"
                      value=""
                      onChange={(e) => e.target.value && patchPriority(c.id, e.target.value)}
                    >
                      <option value="">Priority…</option>
                      {PRIORITIES.map((p) => (
                        <option key={p}>{p}</option>
                      ))}
                    </select>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {detail && (
        <div
          className="fixed inset-0 bg-black/40 grid place-items-center p-4"
          onClick={() => setDetail(null)}
        >
          <div className="bg-white rounded-xl max-w-lg w-full p-6" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <Badge value={detail.status} />
              <Badge value={detail.priority} />
            </div>
            <p className="font-semibold text-slate-900">{detail.category}</p>
            <p className="mt-1 text-sm text-slate-600 whitespace-pre-wrap">
              {detail.description}
            </p>
            {detail.photo_url ? (
              <img
                src={detail.photo_url}
                alt="attachment"
                className="mt-3 rounded-lg max-h-48 object-cover"
              />
            ) : null}

            <h3 className="mt-5 mb-2 text-sm font-semibold text-slate-700">History</h3>
            {(detail.history || []).length === 0 ? (
              <Empty />
            ) : (
              <ol className="space-y-1.5 text-sm text-slate-600">
                {detail.history.map((h, i) => (
                  <li key={i}>
                    <span className="font-medium">{h.new_status || h.status}</span>{" "}
                    - {h.note || "no note"}{" "}
                    <span className="text-xs text-slate-400">
                      {new Date(h.changed_at).toLocaleString()}
                    </span>
                  </li>
                ))}
              </ol>
            )}

            {isStaff && detail.status !== "RESOLVED" && (
              <div className="mt-5 flex gap-2">
                {detail.status === "OPEN" && (
                  <button
                    className="btn-secondary"
                    onClick={() => patchStatus(detail.id, "IN_PROGRESS", "")}
                  >
                    Start work
                  </button>
                )}
                <button
                  className="btn-primary"
                  onClick={() => {
                    const note = prompt("Resolution note:");
                    if (note !== null) patchStatus(detail.id, "RESOLVED", note);
                  }}
                >
                  Mark resolved
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
