import React from "react";
import { getAdminReports } from "../api/dashboards";
import Toast from "../components/Toast.jsx";
import { useAuth } from "../context/AuthContext";
import useApiData from "../hooks/useApiData";

function toUsd(amount) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(amount ?? 0);
}

export default function AdminReportsPage() {
  const { token } = useAuth();
  const { data, loading, error } = useApiData(() => getAdminReports(token), [token]);
  const rows = data?.rows || [];

  return (
    <section className="card">
      <h2>Commission Reports</h2>
      <p className="note">Admin finance summary (TC-025 shell).</p>
      {loading ? <p className="note">Loading report rows...</p> : null}
      <Toast message={error} tone="danger" />
      {!loading && !error && rows.length === 0 ? <p className="note">No report records.</p> : null}
      <table>
        <thead>
          <tr><th>Date</th><th>Orders</th><th>Gross</th><th>Commission</th></tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.date}>
              <td>{r.date}</td>
              <td>{r.orders}</td>
              <td>{toUsd(r.gross)}</td>
              <td>{toUsd(r.commission)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
