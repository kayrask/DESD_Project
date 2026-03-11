import React from "react";
import { getAdminUsers } from "../api/dashboards";
import StatusPill from "../components/StatusPill.jsx";
import Toast from "../components/Toast.jsx";
import { useAuth } from "../context/AuthContext";
import useApiData from "../hooks/useApiData";

export default function AdminUsersPage() {
  const { token } = useAuth();
  const { data, loading, error } = useApiData(() => getAdminUsers(token), [token]);
  const rows = data?.items || [];

  return (
    <section className="card">
      <h2>Users</h2>
      <p className="note">Role and account status overview.</p>
      {loading ? <p className="note">Loading users...</p> : null}
      <Toast message={error} tone="danger" />
      {!loading && !error && rows.length === 0 ? <p className="note">No users found.</p> : null}
      <table>
        <thead>
          <tr><th>Email</th><th>Role</th><th>Status</th></tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.email}>
              <td>{r.email}</td>
              <td>{r.role}</td>
              <td><StatusPill value={r.status} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
