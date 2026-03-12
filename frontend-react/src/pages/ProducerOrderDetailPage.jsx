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

          <h3 style={{ marginTop: 18 }}>Order Items</h3>
          {Array.isArray(data.items) && data.items.length > 0 ? (
            <>
              <table>
                <thead>
                  <tr>
                    <th>Product</th>
                    <th>Qty</th>
                    <th>Unit Price</th>
                    <th>Line Total</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((item) => (
                    <tr key={item.id ?? `${item.product_id}-${item.name}`}>
                      <td>{item.name}</td>
                      <td>{item.quantity}</td>
                      <td>${Number(item.unit_price || 0).toFixed(2)}</td>
                      <td>${Number(item.line_total || 0).toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p style={{ marginTop: 10 }}>
                <strong>Order Total:</strong> ${Number(data.order_total || 0).toFixed(2)}
              </p>
            </>
          ) : (
            <p className="note">
              {data.items_available
                ? "No item rows found for this order yet."
                : "Order item breakdown is not available in the current database schema."}
            </p>
          )}
        </div>
      ) : null}
      <Link className="btn secondary" to="/producer/orders">Back to Orders</Link>
    </section>
  );
}
