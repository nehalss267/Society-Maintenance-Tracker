import { useEffect, useState } from "react";
import api, { errDetail } from "../services/api";
import { Empty, ErrorBox, Stat } from "../components/ui";

export default function Reports() {
  const [expenses, setExpenses] = useState(null);
  const [collections, setCollections] = useState(null);
  const [period, setPeriod] = useState("");
  const [error, setError] = useState(null);

  useEffect(() => {
    const qs = period ? `?period=${period}` : "";
    Promise.all([
      api.get("/api/admin/reports/expenses"),
      api.get(`/api/admin/reports/collections${qs}`),
    ])
      .then(([e, c]) => {
        setExpenses(e.data);
        setCollections(c.data);
      })
      .catch((err) => setError(errDetail(err)));
  }, [period]);

  if (error) return <ErrorBox message={error} />;
  if (!expenses || !collections) return <Empty>Loading reports…</Empty>;

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-900 mb-6">Reports</h1>

      <div className="card mb-6">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold text-slate-900">Collections</h2>
          <input
            className="input w-40"
            placeholder="YYYY-MM"
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <Stat label={`Billed (${collections.period})`} value={`₹${collections.billed_total.toLocaleString("en-IN")}`} />
          <Stat
            label="Collected"
            value={`₹${collections.collected_total.toLocaleString("en-IN")}`}
            accent="text-emerald-600"
          />
        </div>

        <table className="w-full mt-4">
          <thead>
            <tr>
              <th className="th">Outstanding by status</th>
              <th className="th text-right">Amount</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(collections.outstanding_by_status).map(([s, amt]) => (
              <tr key={s}>
                <td className="td">{s.replace(/_/g, " ")}</td>
                <td className="td text-right font-mono">
                  ₹{amt.toLocaleString("en-IN")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h2 className="font-semibold text-slate-900 mb-3">Expenses by category</h2>
        {expenses.rows.length === 0 ? (
          <Empty>No expenses recorded.</Empty>
        ) : (
          <>
            <table className="w-full">
              <thead>
                <tr>
                  <th className="th">Category</th>
                  <th className="th text-right">Count</th>
                  <th className="th text-right">Total</th>
                </tr>
              </thead>
              <tbody>
                {expenses.rows.map((r) => (
                  <tr key={r.category}>
                    <td className="td">{r.category}</td>
                    <td className="td text-right">{r.count}</td>
                    <td className="td text-right font-mono">
                      ₹{r.total.toLocaleString("en-IN")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-3 text-sm font-semibold text-slate-700 text-right">
              Grand total: ₹{expenses.grand_total.toLocaleString("en-IN")}
            </p>
          </>
        )}
      </div>
    </div>
  );
}
