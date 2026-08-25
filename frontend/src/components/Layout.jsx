import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const NAV = [
  {
    section: "General",
    items: [
      { to: "/dashboard", label: "Dashboard", roles: ["RESIDENT"] },
      { to: "/staff", label: "Committee Desk", roles: ["COMMITTEE", "ADMIN"] },
      { to: "/accounting-dash", label: "Finance Desk", roles: ["ACCOUNTANT", "ADMIN"] },
      { to: "/complaints", label: "Complaints", roles: ["RESIDENT", "COMMITTEE", "ACCOUNTANT", "ADMIN"] },
      { to: "/notices", label: "Notices", roles: ["RESIDENT", "COMMITTEE", "ACCOUNTANT", "ADMIN"] },
      { to: "/invoices", label: "My Invoices", roles: ["RESIDENT"] },
      { to: "/settings", label: "Settings", roles: ["RESIDENT", "COMMITTEE", "ACCOUNTANT", "ADMIN"] },
    ],
  },
  {
    section: "Administration",
    items: [
      { to: "/admin/users", label: "Users & Roles", roles: ["ADMIN"] },
      { to: "/admin/billing", label: "Billing", roles: ["ACCOUNTANT", "ADMIN"] },
      { to: "/admin/accounting", label: "Expenses & Fund", roles: ["ACCOUNTANT", "ADMIN"] },
      { to: "/admin/reports", label: "Reports", roles: ["ACCOUNTANT", "ADMIN"] },
    ],
  },
];

export default function Layout() {
  const { auth, logout } = useAuth();
  const navigate = useNavigate();
  const role = auth?.user?.role;

  return (
    <div className="min-h-screen flex">
      <aside className="w-60 shrink-0 bg-slate-900 text-slate-200 flex flex-col">
        <div className="px-5 py-5 border-b border-slate-800">
          <p className="font-bold text-white leading-tight">SMT</p>
          <p className="text-xs text-slate-400">Society Maintenance Tracker</p>
        </div>

        <nav className="flex-1 overflow-y-auto py-3">
          {NAV.map((group) => {
            const visible = group.items.filter((i) => i.roles.includes(role));
            if (!visible.length) return null;
            return (
              <div key={group.section} className="mb-4">
                <p className="px-5 mb-1 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                  {group.section}
                </p>
                {visible.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.end}
                    className={({ isActive }) =>
                      `block px-5 py-2 text-sm ${
                        isActive
                          ? "bg-indigo-600/90 text-white"
                          : "text-slate-300 hover:bg-slate-800"
                      }`
                    }
                  >
                    {item.label}
                  </NavLink>
                ))}
              </div>
            );
          })}
        </nav>

        <div className="px-5 py-4 border-t border-slate-800 text-sm">
          <p className="text-white font-medium">{auth?.user?.name}</p>
          <p className="text-xs text-slate-400 mb-2">{role}</p>
          <button
            onClick={() => {
              logout();
              navigate("/login");
            }}
            className="text-xs text-slate-400 hover:text-white"
          >
            Sign out
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto p-8 max-w-6xl mx-auto w-full">
        <Outlet />
      </main>
    </div>
  );
}
