import React from "react";
import { getProducerProducts } from "../api/dashboards";
import Toast from "../components/Toast.jsx";
import StatusPill from "../components/StatusPill.jsx";
import { useAuth } from "../context/AuthContext";
import useApiData from "../hooks/useApiData";

export default function ProducerProductsPage() {
  const { token } = useAuth();
  const { data, loading, error } = useApiData(() => getProducerProducts(token), [token]);
  const rows = data?.items || [];

  return (
    <section className="card">
      <h2>Products</h2>
      <p className="note">Producer inventory management shell.</p>
      {loading ? <p className="note">Loading products...</p> : null}
      <Toast message={error} tone="danger" />
      {!loading && !error && rows.length === 0 ? <p className="note">No products found.</p> : null}
      <table>
        <thead>
          <tr><th>Name</th><th>Category</th><th>Price</th><th>Stock</th><th>Status</th></tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.name}>
              <td>{r.name}</td>
              <td>{r.category}</td>
              <td>{r.price}</td>
              <td>{r.stock}</td>
              <td><StatusPill value={r.status} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
