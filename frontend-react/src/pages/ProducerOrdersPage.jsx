import React from "react";
import { getProducerOrders } from "../api/dashboards";
import StatusPill from "../components/StatusPill.jsx";
import Toast from "../components/Toast.jsx";
import { useAuth } from "../context/AuthContext";
import useApiData from "../hooks/useApiData";

export default function ProducerOrdersPage() {
  const { token } = useAuth();
  const { data, loading, error } = useApiData(() => getProducerOrders(token), [token]);
  const rows = data?.items || [];

  return (
    <section className="card">
      <h2>Orders</h2>
      <p className="note">Status workflow: Pending -&gt; Confirmed -&gt; Ready -&gt; Delivered.</p>
      {loading ? <p className="note">Loading orders...</p> : null}
      <Toast message={error} tone="danger" />
      {!loading && !error && rows.length === 0 ? <p className="note">No incoming orders.</p> : null}
      <table>
        <thead>
          <tr><th>Order</th><th>Customer</th><th>Delivery</th><th>Status</th></tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.order_id}>
              <td>{r.order_id}</td>
              <td>{r.customer}</td>
              <td>{r.delivery}</td>
              <td><StatusPill value={r.status} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
