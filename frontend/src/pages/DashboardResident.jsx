import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api, { errDetail } from "../services/api";
import { Stat, Empty, ErrorBox } from "../components/ui";

export default function DashboardResident() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api
      .get("/api/dashboard/resident")
      .then((r) => setData(r.data))
      .catch((e) => setError(errDetail(e)));
  }, []);

  if (error) return <ErrorBox message={error} />;
  if (!data) return <Empty>Loading dashboard…</Empty>;

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-900 mb-6">
        Welcome home 👋
      </h1>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Stat label="Open complaints" value={data.complaints.open} />
        <Stat label="Resolved complaints" value={data.complaints.resolved} />
        <Stat
          label="Unpaid invoices"
          value={data.billing.unpaid_count}
          accent={
            data.billing.unpaid_count > 0 ? "text-amber-600" : "text-emerald-600"
          }
        />
        <Stat
          label="Outstanding"
          value={`₹${data.billing.outstanding_amount.toLocaleString("en-IN")}`}
          sub={`${data.billing.overdue_count} overdue`}
          accent={
            data.billing.outstanding_amount > 0 ? "text-rose-600" : "text-emerald-600"
          }
        />
      </div>

      <div className="mt-8 grid md:grid-cols-2 gap-6">
        <div className="card">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold text-slate-900">Quick actions</h2>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link to="/complaints" className="btn-primary">New complaint</Link>
            <Link to="/invoices" className="btn-secondary">Pay maintenance</Link>
            <Link to="/notices" className="btn-secondary">View notices</Link>
          </div>
        </div>

        <div className="card">
          <h2 className="font-semibold text-slate-900 mb-3">Important notices</h2>
          {data.important_notices.length === 0 ? (
            <Empty>No important notices.</Empty>
          ) : (
            <ul className="space-y-2">
              {data.important_notices.map((n) => (
                <li key={n.id} className="flex items-center gap-2 text-sm">
                  <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 shrink-0" />
                  <span className="text-slate-700">{n.title}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
