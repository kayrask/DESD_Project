import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getProducerOrders, updateProducerOrderStatus } from "../api/dashboards";
import { getApiMessage } from "../api/client";
import StatusPill from "../components/StatusPill.jsx";
import Toast from "../components/Toast.jsx";
import { useAuth } from "../context/AuthContext";

const nextStatusOptions = {
  pending: ["Confirmed"],
  confirmed: ["Ready"],
  ready: ["Delivered"],
  delivered: [],
};

export default function ProducerOrdersPage() {
  const { token } = useAuth();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [statusDrafts, setStatusDrafts] = useState({});

  const getAllowedOptions = (currentStatus) => {
    const key = String(currentStatus || "").toLowerCase();
    return nextStatusOptions[key] || [];
  };

  const loadOrders = async () => {
    setLoading(true);
    setError("");
    const response = await getProducerOrders(token);
    if (!response.ok) {
      setRows([]);
      setError(getApiMessage(response.data, `Request failed (${response.status})`));
    } else {
      const items = response.data?.items || [];
      setRows(items);
      setStatusDrafts(
        items.reduce((acc, item) => {
          const allowed = getAllowedOptions(item.status);
          if (allowed.length > 0) {
            acc[item.order_id] = allowed[0];
          }
          return acc;
        }, {}),
      );
    }
    setLoading(false);
  };

  useEffect(() => {
    loadOrders();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const handleStatusUpdate = async (orderId) => {
    const next = statusDrafts[orderId];
    setError("");
    setMessage("");
    const response = await updateProducerOrderStatus(orderId, next, token);
    if (!response.ok) {
      setError(getApiMessage(response.data, "Failed to update order status"));
      return;
    }
    setMessage(`Order ${orderId} status updated to ${next}.`);
    await loadOrders();
  };

  return (
    <section className="card">
      <h2>Orders</h2>
      <p className="note">Status workflow: Pending -&gt; Confirmed -&gt; Ready -&gt; Delivered.</p>
      {loading ? <p className="note">Loading orders...</p> : null}
      <Toast message={error} tone="danger" />
      <Toast message={message} tone="info" />
      {!loading && !error && rows.length === 0 ? <p className="note">No incoming orders.</p> : null}
      <table>
        <thead>
          <tr><th>Order</th><th>Customer</th><th>Delivery</th><th>Status</th><th>Update</th><th>Detail</th></tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.order_id}>
              <td>{r.order_id}</td>
              <td>{r.customer}</td>
              <td>{r.delivery}</td>
              <td><StatusPill value={r.status} /></td>
              <td style={{ minWidth: 220 }}>
                <div style={{ display: "flex", gap: 8 }}>
                  {getAllowedOptions(r.status).length > 0 ? (
                    <>
                      <select
                        className="input"
                        value={
                          getAllowedOptions(r.status).includes(statusDrafts[r.order_id])
                            ? statusDrafts[r.order_id]
                            : getAllowedOptions(r.status)[0]
                        }
                        onChange={(e) =>
                          setStatusDrafts((prev) => ({
                            ...prev,
                            [r.order_id]: e.target.value,
                          }))
                        }
                      >
                        {getAllowedOptions(r.status).map((option) => (
                          <option key={option} value={option}>
                            {option}
                          </option>
                        ))}
                      </select>
                      <button type="button" className="btn secondary" onClick={() => handleStatusUpdate(r.order_id)}>
                        Save
                      </button>
                    </>
                  ) : (
                    <span className="note">Final status reached</span>
                  )}
                </div>
              </td>
              <td>
                <Link className="btn secondary" to={`/producer/orders/${encodeURIComponent(r.order_id)}`}>
                  View
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
