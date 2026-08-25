import { useEffect, useState } from "react";
import api, { errDetail } from "../services/api";
import { Badge, Empty, ErrorBox } from "../components/ui";

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
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {users.map((u) => (
              <tr key={u.id} className="hover:bg-slate-50">
                <td className="td font-medium">{u.name}</td>
                <td className="td text-slate-500">{u.email}</td>
                <td className="td"><Badge value={u.role} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
