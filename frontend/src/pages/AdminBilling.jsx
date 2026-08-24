import { useEffect, useState } from "react";
import api, { errDetail } from "../services/api";
import { Badge, Empty, ErrorBox, Stat } from "../components/ui";

export default function AdminBilling() {
  const [plans, setPlans] = useState([]);
  const [invoices, setInvoices] = useState([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [period, setPeriod] = useState("");
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);

  const [planForm, setPlanForm] = useState({
    name: "",
    amount: "",
    cycle: "MONTHLY",
    due_day_of_month: 10,
    late_fee_amount: 100,
    late_fee_grace_days: 3,
  });

  const loadPlans = () =>
    api
      .get("/api/admin/plans")
      .then((r) => setPlans(r.data))
      .catch((e) => setError(errDetail(e)));

  const loadInvoices = () => {
    const params = {};
    if (statusFilter) params.status = statusFilter;
    if (period) params.period = period;
    return api
      .get("/api/admin/invoices", { params })
      .then((r) => setInvoices(r.data.items || []))
      .catch((e) => setError(errDetail(e)));
  };

  useEffect(() => {
    loadPlans();
    loadInvoices();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter, period]);

  const createPlan = async (e) => {
    e.preventDefault();
    setError(null);
    try {
      await api.post("/api/admin/plans", {
        ...planForm,
        amount: parseFloat(planForm.amount),
        due_day_of_month: parseInt(planForm.due_day_of_month),
        late_fee_amount: parseFloat(planForm.late_fee_amount),
        late_fee_grace_days: parseInt(planForm.late_fee_grace_days),
      });
      setPlanForm({ ...planForm, name: "", amount: "" });
      loadPlans();
    } catch (err) {
      setError(errDetail(err));
    }
  };

  const runBilling = async () => {
    const p = prompt("Billing period (YYYY-MM):", new Date().toISOString().slice(0, 7));
    if (!p) return;
    try {
      const r = await api.post(`/api/admin/billing/run/${p}`);
      setNotice(`Created ${r.data.length ?? "?"} invoices for ${p}.`);
      loadInvoices();
    } catch (err) {
      alert(errDetail(err));
    }
  };

  const runLateFees = async () => {
    try {
      const r = await api.post("/api/admin/billing/late-fees");
      setNotice(`Applied ${r.data.length ?? 0} late fees.`);
      loadInvoices();
    } catch (err) {
      alert(errDetail(err));
    }
  };

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-900 mb-6">Billing</h1>
      <ErrorBox message={error} />
      {notice && (
        <div className="mb-4 rounded-lg bg-emerald-50 border border-emerald-200 px-4 py-2 text-sm text-emerald-700">
          {notice}
        </div>
      )}

      <div className="flex gap-2 mb-6">
        <button className="btn-primary" onClick={runBilling}>Run billing…</button>
        <button className="btn-secondary" onClick={runLateFees}>Apply late fees</button>
      </div>

      <div className="card mb-6">
        <h2 className="font-semibold text-slate-900 mb-3">Maintenance plans</h2>
        {plans.length === 0 ? (
          <Empty>No plans yet - create one below.</Empty>
        ) : (
          <ul className="divide-y divide-slate-100 mb-4">
            {plans.map((p) => (
              <li key={p.id} className="py-2 flex items-center justify-between text-sm">
                <span className="font-medium">{p.name}</span>
                <span>₹{parseFloat(p.amount).toLocaleString("en-IN")} · {p.cycle} · day {p.due_day_of_month}</span>
              </li>
            ))}
          </ul>
        )}

        <form onSubmit={createPlan} className="grid grid-cols-3 lg:grid-cols-6 gap-2 items-end">
          <input
            className="input col-span-2"
            placeholder="Plan name"
            required
            value={planForm.name}
            onChange={(e) => setPlanForm({ ...planForm, name: e.target.value })}
          />
          <input
            className="input"
            type="number"
            step="0.01"
            placeholder="Amount"
            required
            value={planForm.amount}
            onChange={(e) => setPlanForm({ ...planForm, amount: e.target.value })}
          />
          <input
            className="input"
            type="number"
            min="1"
            max="28"
            placeholder="Due day"
            value={planForm.due_day_of_month}
            onChange={(e) => setPlanForm({ ...planForm, due_day_of_month: e.target.value })}
          />
          <input
            className="input"
            type="number"
            placeholder="Late fee"
            value={planForm.late_fee_amount}
            onChange={(e) => setPlanForm({ ...planForm, late_fee_amount: e.target.value })}
          />
          <button className="btn-primary">Add plan</button>
        </form>
      </div>

      <div className="flex gap-2 mb-4">
        <select
          className="input w-44"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        >
          <option value="">All statuses</option>
          <option>PENDING</option>
          <option>PARTIALLY_PAID</option>
          <option>PAID</option>
          <option>OVERDUE</option>
          <option>CANCELLED</option>
        </select>
        <input
          className="input w-40"
          placeholder="YYYY-MM"
          value={period}
          onChange={(e) => setPeriod(e.target.value)}
        />
      </div>

      {invoices.length === 0 ? (
        <Empty>No invoices match.</Empty>
      ) : (
        <table className="w-full bg-white rounded-xl border border-slate-200 overflow-hidden">
          <thead className="bg-slate-50">
            <tr>
              <th className="th">Invoice</th>
              <th className="th">Resident</th>
              <th className="th">Period</th>
              <th className="th">Total</th>
              <th className="th">Paid</th>
              <th className="th">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {invoices.map((i) => (
              <tr key={i.id}>
                <td className="td font-mono text-xs">{i.invoice_number}</td>
                <td className="td">{i.resident_name || i.resident_email}</td>
                <td className="td">{i.billing_period}</td>
                <td className="td">₹{parseFloat(i.total_amount).toLocaleString("en-IN")}</td>
                <td className="td">₹{parseFloat(i.amount_paid).toLocaleString("en-IN")}</td>
                <td className="td"><Badge value={i.status} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
