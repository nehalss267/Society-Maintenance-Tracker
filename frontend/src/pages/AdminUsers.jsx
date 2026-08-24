import { useEffect, useState } from "react";
import api, { errDetail } from "../services/api";
import { Badge, Empty, ErrorBox } from "../components/ui";

const ROLES = ["RESIDENT", "COMMITTEE", "ACCOUNTANT", "ADMIN"];

export default function AdminUsers() {
  const [users, setUsers] = useState([]);
  const [search, setSearch] = useState("");
  const [error, setError] = useState(null);

  const load = () =>
    api
      .get("/api/admin/users", { params: search ? { search } : {} })
      .then((r) => setUsers(r.data.items || r.data))
      .catch((e) => setError(errDetail(e)));

  useEffect(load, [search]);

  const changeRole = async (id, role) => {
    try {
      await api.patch(`/api/admin/users/${id}/role`, { new_role: role });
      load();
    } catch (err) {
      alert(errDetail(err));
    }
  };

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-900 mb-6">Users & Roles</h1>
      <ErrorBox message={error} />

      <input
        className="input max-w-sm mb-4"
        placeholder="Search name or email…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />

      {users.length === 0 ? (
        <Empty>No users match.</Empty>
      ) : (
        <table className="w-full bg-white rounded-xl border border-slate-200 overflow-hidden">
          <thead className="bg-slate-50">
            <tr>
              <th className="th">Name</th>
              <th className="th">Email</th>
              <th className="th">Role</th>
              <th className="th">Change role</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {users.map((u) => (
              <tr key={u.id} className="hover:bg-slate-50">
                <td className="td font-medium">{u.name}</td>
                <td className="td text-slate-500">{u.email}</td>
                <td className="td"><Badge value={u.role} /></td>
                <td className="td">
                  <select
                    className="text-xs border rounded px-2 py-1"
                    value={u.role}
                    onChange={(e) => changeRole(u.id, e.target.value)}
                  >
                    {ROLES.map((r) => (
                      <option key={r}>{r}</option>
                    ))}
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
