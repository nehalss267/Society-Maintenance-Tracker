import { useEffect, useState } from "react";
import api, { errDetail } from "../services/api";
import { Badge, Empty, ErrorBox, Stat } from "../components/ui";

export default function Invoices() {
  const [invoices, setInvoices] = useState([]);
  const [error, setError] = useState(null);
  const [paying, setPaying] = useState(null);
  const [notice, setNotice] = useState(null);

  const load = () =>
    api
      .get("/api/invoices")
      .then((r) => setInvoices(r.data))
      .catch((e) => setError(errDetail(e)));

  useEffect(load, []);

  const unpaid = invoices.filter((i) => ["PENDING", "OVERDUE", "PARTIALLY_PAID"].includes(i.status));

  const pay = async (invoice) => {
    setPaying(invoice.id);
    setError(null);
    try {
      const init = await api.post("/api/payments/initiate", {
        invoice_id: invoice.id,
      });

      if (init.data.mode === "simulated") {
        // Fallback capture when Razorpay keys are not configured
        await api.post("/api/payments/simulate-success", {
          payment_id: init.data.payment_id,
        });
        setNotice(`Paid ₹${init.data.amount} for ${invoice.invoice_number} (demo mode).`);
      } else {
        alert(
          `Razorpay checkout would open here for order ${init.data.order_id}. ` +
            "Configure RAZORPAY_KEY_ID/SECRET on the backend to enable real payments."
        );
      }
      load();
    } catch (err) {
      setError(errDetail(err));
    } finally {
      setPaying(null);
    }
  };

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-900 mb-6">My Invoices</h1>
      <ErrorBox message={error} />
      {notice && (
        <div className="mb-4 rounded-lg bg-emerald-50 border border-emerald-200 px-4 py-2 text-sm text-emerald-700">
          {notice}
        </div>
      )}

      <div className="grid grid-cols-3 gap-4 mb-6">
        <Stat label="Total invoices" value={invoices.length} />
        <Stat
          label="Unpaid"
          value={unpaid.length}
          accent={unpaid.length ? "text-amber-600" : "text-emerald-600"}
        />
        <Stat
          label="Outstanding"
          value={`₹${unpaid
            .reduce((s, i) => s + parseFloat(i.total_amount) - parseFloat(i.amount_paid), 0)
            .toLocaleString("en-IN")}`}
        />
      </div>

      {invoices.length === 0 ? (
        <Empty>No invoices yet.</Empty>
      ) : (
        <table className="w-full bg-white rounded-xl border border-slate-200 overflow-hidden">
          <thead className="bg-slate-50">
            <tr>
              <th className="th">Invoice</th>
              <th className="th">Period</th>
              <th className="th">Total</th>
              <th className="th">Paid</th>
              <th className="th">Due</th>
              <th className="th">Status</th>
              <th className="th"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {invoices.map((i) => {
              const outstanding =
                parseFloat(i.total_amount) - parseFloat(i.amount_paid);

              return (
                <tr key={i.id} className="hover:bg-slate-50">
                  <td className="td font-mono text-xs">{i.invoice_number}</td>
                  <td className="td">{i.billing_period}</td>
                  <td className="td">₹{parseFloat(i.total_amount).toLocaleString("en-IN")}</td>
                  <td className="td">₹{parseFloat(i.amount_paid).toLocaleString("en-IN")}</td>
                  <td className="td">{i.due_date}</td>
                  <td className="td"><Badge value={i.status} /></td>
                  <td className="td">
                    {outstanding > 0 && i.status !== "CANCELLED" ? (
                      <button
                        className="btn-primary !py-1 !px-3 text-xs"
                        disabled={paying === i.id}
                        onClick={() => pay(i)}
                      >
                        {paying === i.id ? "Processing…" : `Pay ₹${outstanding.toLocaleString("en-IN")}`}
                      </button>
                    ) : null}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
