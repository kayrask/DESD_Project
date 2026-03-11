import React from "react";
import { Link } from "react-router-dom";
import { getAdminSummary } from "../api/dashboards";
import Badge from "../components/Badge.jsx";
import Toast from "../components/Toast.jsx";
import { useAuth } from "../context/AuthContext";
import useApiData from "../hooks/useApiData";

export default function AdminDashboard() {
  const { token } = useAuth();
  const { data, loading, error } = useApiData(() => getAdminSummary(token), [token]);

  return (
    <section className="card">
      <h2>Admin Dashboard</h2>
      <p className="note">Operational summary with quick links to reports, users, and database checks.</p>
      {loading ? <p className="note">Loading admin metrics...</p> : null}
      <Toast message={error} tone="danger" />
      {data ? (
        <p className="note">
          <Badge tone="success">Commission today: ${data.commission_today}</Badge>{" "}
          <Badge tone="default">Active users: {data.active_users}</Badge>{" "}
          <Badge tone="warning">Open flags: {data.open_flags}</Badge>
        </p>
      ) : null}
      <div className="grid">
        <Link className="tile" to="/admin/reports">Commission Reports</Link>
        <Link className="tile" to="/admin/users">Users</Link>
        <Link className="tile" to="/admin/database">Database Contents</Link>
      </div>
    </section>
  );
}
