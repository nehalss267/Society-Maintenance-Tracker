import { useEffect, useState } from "react";
import api, { errDetail } from "../services/api";
import { Stat, Empty, ErrorBox } from "../components/ui";

export default function DashboardAccountant() {
  const [data, setData] = useState(null);
  const [period, setPeriod] = useState("");
  const [error, setError] = useState(null);

  useEffect(() => {
    const qs = period ? `?period=${period}` : "";
    api
      .get(`/api/dashboard/accountant${qs}`)
      .then((r) => setData(r.data))
      .catch((e) => setError(errDetail(e)));
  }, [period]);

  if (error) return <ErrorBox message={error} />;
  if (!data) return <Empty>Loading finance desk…</Empty>;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Finance desk</h1>
        <input
          className="input w-40"
          placeholder="YYYY-MM"
          value={period}
          onChange={(e) => setPeriod(e.target.value)}
        />
      </div>

      <p className="text-xs text-slate-400 mb-4">Billing period: {data.period}</p>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Stat label="Billed" value={`₹${data.invoices.billed.toLocaleString("en-IN")}`} />
        <Stat
          label="Collected"
          value={`₹${data.invoices.collected.toLocaleString("en-IN")}`}
          accent="text-emerald-600"
        />
        <Stat
          label="Outstanding"
          value={`₹${data.invoices.outstanding.toLocaleString("en-IN")}`}
          accent={data.invoices.outstanding > 0 ? "text-rose-600" : "text-emerald-600"}
          sub={`${data.invoices.overdue} overdue`}
        />
        <Stat
          label="Fund balance"
          value={`₹${data.fund_balance.toLocaleString("en-IN")}`}
          accent="text-indigo-600"
          sub={`Expenses this month: ₹${data.expenses_this_month.toLocaleString("en-IN")}`}
        />
      </div>
    </div>
  );
}
