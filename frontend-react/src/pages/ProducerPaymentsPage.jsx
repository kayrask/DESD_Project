import React from "react";
import { getProducerPayments } from "../api/dashboards";
import Badge from "../components/Badge.jsx";
import Toast from "../components/Toast.jsx";
import { useAuth } from "../context/AuthContext";
import useApiData from "../hooks/useApiData";

export default function ProducerPaymentsPage() {
  const { token } = useAuth();
  const { data, loading, error } = useApiData(() => getProducerPayments(token), [token]);

  return (
    <section className="card">
      <h2>Payments</h2>
      <p className="note">Weekly settlement summary (TC-012 shell).</p>
      {loading ? <p className="note">Loading payment summary...</p> : null}
      <Toast message={error} tone="danger" />
      <div className="grid">
        <article className="tile"><h3>This Week</h3><p>${data?.this_week ?? "-"}</p><Badge tone="success">Settled</Badge></article>
        <article className="tile"><h3>Pending</h3><p>${data?.pending ?? "-"}</p><Badge tone="warning">Awaiting payout</Badge></article>
        <article className="tile"><h3>Commission</h3><p>${data?.commission ?? "-"}</p><Badge tone="default">Platform fee</Badge></article>
      </div>
    </section>
  );
}
