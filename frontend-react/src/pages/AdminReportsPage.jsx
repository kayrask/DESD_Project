import React, { useEffect, useMemo, useState } from "react";
import { getApiMessage } from "../api/client";
import { getAdminReports } from "../api/dashboards";
import Toast from "../components/Toast.jsx";
import { useAuth } from "../context/AuthContext";

function toUsd(amount) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(amount ?? 0);
}

export default function AdminReportsPage() {
  const { token } = useAuth();
  const [filters, setFilters] = useState({ from: "", to: "" });
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const totals = useMemo(
    () =>
      rows.reduce(
        (acc, row) => ({
          orders: acc.orders + Number(row.orders || 0),
          gross: acc.gross + Number(row.gross || 0),
          commission: acc.commission + Number(row.commission || 0),
        }),
        { orders: 0, gross: 0, commission: 0 },
      ),
    [rows],
  );

  const loadReports = async (activeFilters) => {
    setLoading(true);
    setError("");
    const response = await getAdminReports(token, activeFilters);
    if (!response.ok) {
      setRows([]);
      setError(getApiMessage(response.data, `Request failed (${response.status})`));
    } else {
      setRows(response.data?.rows || []);
    }
    setLoading(false);
  };

  useEffect(() => {
    loadReports(filters);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const handleApply = async (event) => {
    event.preventDefault();
    if (filters.from && filters.to && filters.from > filters.to) {
      setError("Start date cannot be after end date.");
      return;
    }
    await loadReports(filters);
  };

  const handleReset = async () => {
    const resetFilters = { from: "", to: "" };
    setFilters(resetFilters);
    await loadReports(resetFilters);
  };

  return (
    <section className="card">
      <h2>Commission Reports</h2>
      <p className="note">TC-025: Admin report with date range filtering and totals.</p>
      <Toast message={error} tone="danger" />

      <form onSubmit={handleApply} style={{ marginBottom: 14 }}>
        <div className="grid">
          <div>
            <label htmlFor="from">From</label>
            <input
              id="from"
              type="date"
              className="input"
              value={filters.from}
              onChange={(e) => setFilters((prev) => ({ ...prev, from: e.target.value }))}
            />
          </div>
          <div>
            <label htmlFor="to">To</label>
            <input
              id="to"
              type="date"
              className="input"
              value={filters.to}
              onChange={(e) => setFilters((prev) => ({ ...prev, to: e.target.value }))}
            />
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
          <button type="submit" className="btn primary" disabled={loading}>
            {loading ? "Loading..." : "Apply"}
          </button>
          <button type="button" className="btn secondary" onClick={handleReset} disabled={loading}>
            Reset
          </button>
        </div>
      </form>

      <div className="grid" style={{ marginBottom: 14 }}>
        <article className="tile">
          <h3 style={{ margin: 0 }}>Total Orders</h3>
          <p className="note" style={{ marginTop: 6 }}>{totals.orders}</p>
        </article>
        <article className="tile">
          <h3 style={{ margin: 0 }}>Gross Amount</h3>
          <p className="note" style={{ marginTop: 6 }}>{toUsd(totals.gross)}</p>
        </article>
        <article className="tile">
          <h3 style={{ margin: 0 }}>Commission</h3>
          <p className="note" style={{ marginTop: 6 }}>{toUsd(totals.commission)}</p>
        </article>
      </div>

      {loading ? <p className="note">Loading report rows...</p> : null}
      {!loading && !error && rows.length === 0 ? <p className="note">No report records for selected range.</p> : null}

      {!loading && rows.length > 0 ? (
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
      ) : null}
    </section>
  );
}

