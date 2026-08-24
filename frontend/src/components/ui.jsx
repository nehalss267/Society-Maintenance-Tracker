export function Badge({ value }) {
  const styles = {
    OPEN: "bg-amber-100 text-amber-800",
    IN_PROGRESS: "bg-sky-100 text-sky-800",
    RESOLVED: "bg-emerald-100 text-emerald-800",
    PENDING: "bg-amber-100 text-amber-800",
    PARTIALLY_PAID: "bg-sky-100 text-sky-800",
    PAID: "bg-emerald-100 text-emerald-800",
    OVERDUE: "bg-rose-100 text-rose-700",
    CANCELLED: "bg-slate-200 text-slate-600",
    LOW: "bg-slate-100 text-slate-600",
    MEDIUM: "bg-yellow-100 text-yellow-800",
    HIGH: "bg-orange-100 text-orange-700",
    URGENT: "bg-rose-100 text-rose-700",
    RESIDENT: "bg-indigo-100 text-indigo-700",
    COMMITTEE: "bg-violet-100 text-violet-700",
    ACCOUNTANT: "bg-teal-100 text-teal-700",
    ADMIN: "bg-fuchsia-100 text-fuchsia-700",
  };
  return (
    <span
      className={`inline-flex px-2 py-0.5 rounded-full text-xs font-semibold ${
        styles[value] || "bg-slate-100 text-slate-600"
      }`}
    >
      {value?.replace(/_/g, " ")}
    </span>
  );
}

export function Stat({ label, value, sub, accent = "text-slate-900" }) {
  return (
    <div className="card">
      <p className="text-sm text-slate-500">{label}</p>
      <p className={`mt-1 text-2xl font-bold ${accent}`}>{value}</p>
      {sub ? <p className="mt-1 text-xs text-slate-400">{sub}</p> : null}
    </div>
  );
}

export function Empty({ children = "Nothing here yet." }) {
  return (
    <div className="py-10 text-center text-sm text-slate-400">{children}</div>
  );
}

export function ErrorBox({ message }) {
  if (!message) return null;
  return (
    <div className="mb-4 rounded-lg bg-rose-50 border border-rose-200 px-4 py-2 text-sm text-rose-700">
      {String(message)}
    </div>
  );
}
