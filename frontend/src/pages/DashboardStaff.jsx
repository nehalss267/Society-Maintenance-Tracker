import { useEffect, useState } from "react";
import api, { errDetail } from "../services/api";
import { Stat, Empty, ErrorBox, Badge } from "../components/ui";

export default function DashboardStaff() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api
      .get("/api/dashboard/staff")
      .then((r) => setData(r.data))
      .catch((e) => setError(errDetail(e)));
  }, []);

  if (error) return <ErrorBox message={error} />;
  if (!data) return <Empty>Loading committee desk…</Empty>;

  const statuses = Object.entries(data.complaints_by_status);
  const priorities = Object.entries(data.complaints_by_priority);

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-900 mb-6">Committee desk</h1>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Stat
          label="Open complaints"
          value={data.complaints_by_status.OPEN || 0}
          accent="text-amber-600"
        />
        <Stat label="SLA breached" value={data.sla_breached} accent="text-rose-600" />
        <Stat label="Total residents" value={data.total_residents} />
        <Stat label="Resolved" value={data.complaints_by_status.RESOLVED || 0} accent="text-emerald-600" />
      </div>

      <div className="mt-8 grid md:grid-cols-2 gap-6">
        <div className="card">
          <h2 className="font-semibold text-slate-900 mb-3">By status</h2>
          {statuses.length === 0 ? (
            <Empty />
          ) : (
            <ul className="space-y-2">
              {statuses.map(([s, c]) => (
                <li key={s} className="flex items-center justify-between text-sm">
                  <Badge value={s} />
                  <span className="font-semibold">{c}</span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="card">
          <h2 className="font-semibold text-slate-900 mb-3">By priority</h2>
          {priorities.length === 0 ? (
            <Empty />
          ) : (
            <ul className="space-y-2">
              {priorities.map(([p, c]) => (
                <li key={p} className="flex items-center justify-between text-sm">
                  <Badge value={p} />
                  <span className="font-semibold">{c}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
