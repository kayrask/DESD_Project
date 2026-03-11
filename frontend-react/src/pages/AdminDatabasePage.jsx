import React from "react";
import { getAdminDatabase } from "../api/dashboards";
import StatusPill from "../components/StatusPill.jsx";
import Toast from "../components/Toast.jsx";
import { useAuth } from "../context/AuthContext";
import useApiData from "../hooks/useApiData";

export default function AdminDatabasePage() {
  const { token } = useAuth();
  const { data, loading, error } = useApiData(() => getAdminDatabase(token), [token]);

  return (
    <section className="card">
      <h2>Database Contents</h2>
      <p className="note">View all database tables for validation.</p>
      {loading ? <p className="note">Loading database...</p> : null}
      <Toast message={error} tone="danger" />

      {data && (
        <>
          <h3>Users</h3>
          {data.users.length === 0 ? <p className="note">No user records.</p> : null}
          <table>
            <thead>
              <tr><th>ID</th><th>Email</th><th>Role</th><th>Full Name</th><th>Status</th></tr>
            </thead>
            <tbody>
              {data.users.map((u) => (
                <tr key={u.id}>
                  <td>{u.id}</td>
                  <td>{u.email}</td>
                  <td>{u.role}</td>
                  <td>{u.full_name}</td>
                  <td><StatusPill value={u.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>

          <h3>Products</h3>
          {data.products.length === 0 ? <p className="note">No product records.</p> : null}
          <table>
            <thead>
              <tr><th>ID</th><th>Name</th><th>Category</th><th>Price</th><th>Stock</th><th>Status</th><th>Producer ID</th></tr>
            </thead>
            <tbody>
              {data.products.map((p) => (
                <tr key={p.id}>
                  <td>{p.id}</td>
                  <td>{p.name}</td>
                  <td>{p.category}</td>
                  <td>${p.price}</td>
                  <td>{p.stock}</td>
                  <td><StatusPill value={p.status} /></td>
                  <td>{p.producer_id}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <h3>Orders</h3>
          {data.orders.length === 0 ? <p className="note">No order records.</p> : null}
          <table>
            <thead>
              <tr><th>ID</th><th>Order ID</th><th>Customer</th><th>Delivery Date</th><th>Status</th><th>Producer ID</th></tr>
            </thead>
            <tbody>
              {data.orders.map((o) => (
                <tr key={o.id}>
                  <td>{o.id}</td>
                  <td>{o.order_id}</td>
                  <td>{o.customer_name}</td>
                  <td>{o.delivery_date}</td>
                  <td><StatusPill value={o.status} /></td>
                  <td>{o.producer_id}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </section>
  );
}
