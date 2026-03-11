import React from "react";
import { Link, useParams } from "react-router-dom";
import { getProducerOrderDetail } from "../api/dashboards";
import StatusPill from "../components/StatusPill.jsx";
import Toast from "../components/Toast.jsx";
import { useAuth } from "../context/AuthContext";
import useApiData from "../hooks/useApiData";

export default function ProducerOrderDetailPage() {
  const { token } = useAuth();
  const { orderId } = useParams();
  const { data, loading, error } = useApiData(
    () => getProducerOrderDetail(orderId, token),
    [orderId, token],
  );

  return (
    <section className="card">
      <h2>Order Detail</h2>
      <p className="note">Order reference: {orderId}</p>
      {loading ? <p className="note">Loading order detail...</p> : null}
      <Toast message={error} tone="danger" />
      {data ? (
        <div>
          <p><strong>Order ID:</strong> {data.order_id}</p>
          <p><strong>Customer:</strong> {data.customer}</p>
          <p><strong>Delivery Date:</strong> {data.delivery}</p>
          <p><strong>Status:</strong> <StatusPill value={data.status} /></p>
        </div>
      ) : null}
      <Link className="btn secondary" to="/producer/orders">Back to Orders</Link>
    </section>
  );
}

