import { useEffect, useState } from "react";
import api, { errDetail } from "../services/api";
import { Badge, Empty, ErrorBox, Stat } from "../components/ui";

export default function AdminAccounting() {
  const [fund, setFund] = useState([]);
  const [txs, setTxs] = useState([]);
  const [expenses, setExpenses] = useState([]);
  const [recurring, setRecurring] = useState([]);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);

  const [expForm, setExpForm] = useState({
    title: "",
    category: "OTHER",
    amount: "",
    expense_date: new Date().toISOString().slice(0, 10),
    vendor: "",
  });
  const [txForm, setTxForm] = useState({ type: "CREDIT", amount: "", description: "" });

  const loadAll = () =>
    Promise.all([
      api.get("/api/admin/funds"),
      api.get("/api/admin/funds/transactions", { params: { limit: 25 } }),
      api.get("/api/admin/expenses", { params: { limit: 25 } }),
      api.get("/api/admin/recurring-expenses"),
    ])
      .then(([f, t, e, r]) => {
        setFund(f.data[0]);
        setTxs(t.data);
        setExpenses(e.data);
        setRecurring(r.data);
      })
      .catch((err) => setError(errDetail(err)));

  useEffect(() => {
    loadAll();
  }, []);

  const createExpense = async (e) => {
    e.preventDefault();
    setError(null);
    try {
      await api.post("/api/admin/expenses", {
        ...expForm,
        amount: parseFloat(expForm.amount),
      });
      setExpForm({ ...expForm, title: "", amount: "", vendor: "" });
      loadAll();
    } catch (err) {
      setError(errDetail(err));
    }
  };

  const uploadReceipt = async (expenseId, file) => {
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    try {
      await api.post(`/api/admin/expenses/${expenseId}/receipt`, fd);
      loadAll();
    } catch (err) {
      alert(errDetail(err));
    }
  };

  const manualTx = async (e) => {
    e.preventDefault();
    try {
      await api.post("/api/admin/funds/transactions", {
        ...txForm,
        amount: parseFloat(txForm.amount),
      });
      setTxForm({ type: txForm.type, amount: "", description: "" });
      loadAll();
    } catch (err) {
      alert(errDetail(err));
    }
  };

  const generateRecurring = async () => {
    const p = prompt("Generate recurring expenses for period (YYYY-MM):",
      new Date().toISOString().slice(0, 7));
    if (!p) return;
    try {
      const r = await api.post(`/api/admin/expenses/generate-recurring/${p}`);
      setNotice(`Generated ${r.data.generated} expenses for ${p}.`);
      loadAll();
    } catch (err) {
      alert(errDetail(err));
    }
  };

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-900 mb-6">Expenses & Fund</h1>
      <ErrorBox message={error} />
      {notice && (
        <div className="mb-4 rounded-lg bg-emerald-50 border border-emerald-200 px-4 py-2 text-sm text-emerald-700">
          {notice}
        </div>
      )}

      {fund ? (
        <div className="grid grid-cols-2 gap-4 mb-6">
          <Stat
            label={`${fund.name} balance`}
            value={`₹${parseFloat(fund.balance).toLocaleString("en-IN")}`}
            accent="text-indigo-600"
          />
          <div className="card">
            <form onSubmit={manualTx} className="flex gap-2 items-end">
              <select
                className="input w-28"
                value={txForm.type}
                onChange={(e) => setTxForm({ ...txForm, type: e.target.value })}
              >
                <option>CREDIT</option>
                <option>DEBIT</option>
              </select>
              <input
                className="input w-28"
                type="number"
                step="0.01"
                placeholder="Amount"
                required
                value={txForm.amount}
                onChange={(e) => setTxForm({ ...txForm, amount: e.target.value })}
              />
              <input
                className="input flex-1"
                placeholder="Reason"
                value={txForm.description}
                onChange={(e) => setTxForm({ ...txForm, description: e.target.value })}
              />
              <button className="btn-primary">Apply</button>
            </form>
          </div>
        </div>
      ) : null}

      <div className="grid lg:grid-cols-2 gap-6">
        <div className="card">
          <h2 className="font-semibold text-slate-900 mb-3">Record expense</h2>
          <form onSubmit={createExpense} className="space-y-2">
            <input
              className="input"
              placeholder="Title"
              required
              value={expForm.title}
              onChange={(e) => setExpForm({ ...expForm, title: e.target.value })}
            />
            <div className="flex gap-2">
              <select
                className="input w-36"
                value={expForm.category}
                onChange={(e) => setExpForm({ ...expForm, category: e.target.value })}
              >
                {["ELECTRICITY", "WATER", "SECURITY", "REPAIRS", "CLEANING", "SALARIES", "OTHER"].map(
                  (c) => (
                    <option key={c}>{c}</option>
                  )
                )}
              </select>
              <input
                className="input"
                type="number"
                step="0.01"
                placeholder="Amount"
                required
                value={expForm.amount}
                onChange={(e) => setExpForm({ ...expForm, amount: e.target.value })}
              />
              <input
                className="input"
                type="date"
                required
                value={expForm.expense_date}
                onChange={(e) => setExpForm({ ...expForm, expense_date: e.target.value })}
              />
            </div>
            <div className="flex gap-2">
              <input
                className="input flex-1"
                placeholder="Vendor (optional)"
                value={expForm.vendor}
                onChange={(e) => setExpForm({ ...expForm, vendor: e.target.value })}
              />
              <button className="btn-primary">Add</button>
            </div>
          </form>

          <h3 className="mt-5 mb-2 text-sm font-semibold text-slate-700">Recent expenses</h3>
          {expenses.length === 0 ? (
            <Empty />
          ) : (
            <ul className="divide-y divide-slate-100 text-sm max-h-64 overflow-y-auto">
              {expenses.map((x) => (
                <li key={x.id} className="py-2 flex items-center justify-between gap-2">
                  <span className="truncate">{x.title}</span>
                  <span className="shrink-0">₹{parseFloat(x.amount).toLocaleString("en-IN")}</span>
                  <label className="text-xs text-indigo-600 cursor-pointer shrink-0">
                    Receipt
                    <input
                      type="file"
                      hidden
                      accept=".pdf,image/jpeg,image/png,image/webp"
                      onChange={(e) => uploadReceipt(x.id, e.target.files[0])}
                    />
                    {x.receipt_file_path ? " ✓" : ""}
                  </label>
                </li>
              ))}
            </ul>
          )}

          <div className="mt-4">
            <button className="btn-secondary text-xs" onClick={generateRecurring}>
              Generate recurring expenses…
            </button>
          </div>
        </div>

        <div className="card">
          <h2 className="font-semibold text-slate-900 mb-3">Fund ledger</h2>
          {txs.length === 0 ? (
            <Empty />
          ) : (
            <ul className="divide-y divide-slate-100 text-sm max-h-96 overflow-y-auto">
              {txs.map((t) => (
                <li key={t.id} className="py-2 flex items-center justify-between gap-2">
                  <span className="truncate text-slate-600">{t.description || t.source}</span>
                  <span
                    className={`font-mono shrink-0 ${
                      t.type === "CREDIT" ? "text-emerald-600" : "text-rose-600"
                    }`}
                  >
                    {t.type === "CREDIT" ? "+" : "-"}
                    ₹{parseFloat(t.amount).toLocaleString("en-IN")}
                  </span>
                  <span className="text-xs text-slate-400 shrink-0 w-20 text-right">
                    ₹{parseFloat(t.balance_after).toLocaleString("en-IN")}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
