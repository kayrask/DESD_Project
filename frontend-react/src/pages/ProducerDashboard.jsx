import React from "react";
import { Link } from "react-router-dom";
import { getProducerSummary } from "../api/dashboards";
import Badge from "../components/Badge.jsx";
import Toast from "../components/Toast.jsx";
import { useAuth } from "../context/AuthContext";
import useApiData from "../hooks/useApiData";

export default function ProducerDashboard() {
  const { token } = useAuth();
  const { data, loading, error } = useApiData(() => getProducerSummary(token), [token]);

  return (
    <section className="card">
      <h2>Producer Dashboard</h2>
      <p>Quick links for Sprint 1.</p>
      {loading ? <p className="note">Loading producer metrics...</p> : null}
      <Toast message={error} tone="danger" />
      {data ? (
        <p className="note">
          <Badge tone="warning">Orders today: {data.orders_today}</Badge>{" "}
          <Badge tone="success">Low stock: {data.low_stock_products}</Badge>
        </p>
      ) : null}
      <div className="grid">
        <Link className="tile" to="/producer/products">Products</Link>
        <Link className="tile" to="/producer/orders">Orders</Link>
        <Link className="tile" to="/producer/payments">Payments</Link>
      </div>
    </section>
  );
}
