import React, { useEffect, useState } from "react";
import {
  createProducerProduct,
  getProducerProducts,
  updateProducerProduct,
} from "../api/dashboards";
import { getApiMessage } from "../api/client";
import Toast from "../components/Toast.jsx";
import StatusPill from "../components/StatusPill.jsx";
import { useAuth } from "../context/AuthContext";

export default function ProducerProductsPage() {
  const { token } = useAuth();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [editingId, setEditingId] = useState(null);
  const [createForm, setCreateForm] = useState({
    name: "",
    category: "",
    price: "",
    stock: "",
    status: "Available",
  });
  const [editForm, setEditForm] = useState({
    name: "",
    category: "",
    price: "",
    stock: "",
    status: "Available",
  });

  const loadProducts = async () => {
    setLoading(true);
    setError("");
    const response = await getProducerProducts(token);
    if (!response.ok) {
      setRows([]);
      setError(getApiMessage(response.data, `Request failed (${response.status})`));
    } else {
      setRows(response.data?.items || []);
    }
    setLoading(false);
  };

  useEffect(() => {
    loadProducts();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const handleCreate = async (event) => {
    event.preventDefault();
    setMessage("");
    setError("");
    const payload = {
      name: createForm.name.trim(),
      category: createForm.category.trim(),
      price: Number(createForm.price),
      stock: Number(createForm.stock),
      status: createForm.status,
    };
    const response = await createProducerProduct(payload, token);
    if (!response.ok) {
      setError(getApiMessage(response.data, "Failed to create product"));
      return;
    }
    setCreateForm({ name: "", category: "", price: "", stock: "", status: "Available" });
    setMessage("Product created successfully.");
    await loadProducts();
  };

  const startEdit = (row) => {
    setEditingId(row.id);
    setEditForm({
      name: row.name || "",
      category: row.category || "",
      price: row.price ?? "",
      stock: row.stock ?? "",
      status: row.status || "Available",
    });
  };

  const handleSaveEdit = async () => {
    if (!editingId) return;
    setMessage("");
    setError("");
    const payload = {
      name: editForm.name.trim(),
      category: editForm.category.trim(),
      price: Number(editForm.price),
      stock: Number(editForm.stock),
      status: editForm.status,
    };
    const response = await updateProducerProduct(editingId, payload, token);
    if (!response.ok) {
      setError(getApiMessage(response.data, "Failed to update product"));
      return;
    }
    setEditingId(null);
    setMessage("Product updated.");
    await loadProducts();
  };

  return (
    <section className="card">
      <h2>Products</h2>
      <p className="note">Create, edit, and manage seasonal stock.</p>
      {loading ? <p className="note">Loading products...</p> : null}
      <Toast message={error} tone="danger" />
      <Toast message={message} tone="info" />

      <form onSubmit={handleCreate} style={{ marginBottom: 16 }}>
        <div className="grid">
          <input
            className="input"
            placeholder="Product name"
            value={createForm.name}
            onChange={(e) => setCreateForm((prev) => ({ ...prev, name: e.target.value }))}
            required
          />
          <input
            className="input"
            placeholder="Category"
            value={createForm.category}
            onChange={(e) => setCreateForm((prev) => ({ ...prev, category: e.target.value }))}
            required
          />
          <input
            className="input"
            type="number"
            step="0.01"
            min="0"
            placeholder="Price"
            value={createForm.price}
            onChange={(e) => setCreateForm((prev) => ({ ...prev, price: e.target.value }))}
            required
          />
          <input
            className="input"
            type="number"
            min="0"
            placeholder="Stock"
            value={createForm.stock}
            onChange={(e) => setCreateForm((prev) => ({ ...prev, stock: e.target.value }))}
            required
          />
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <select
            className="input"
            style={{ maxWidth: 220 }}
            value={createForm.status}
            onChange={(e) => setCreateForm((prev) => ({ ...prev, status: e.target.value }))}
          >
            <option>Available</option>
            <option>Out of Stock</option>
            <option>Seasonal</option>
          </select>
          <button type="submit" className="btn primary">Add Product</button>
        </div>
      </form>

      {!loading && !error && rows.length === 0 ? <p className="note">No products found.</p> : null}
      <table>
        <thead>
          <tr><th>Name</th><th>Category</th><th>Price</th><th>Stock</th><th>Status</th><th>Actions</th></tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id || r.name}>
              <td>{editingId === r.id ? <input className="input" value={editForm.name} onChange={(e) => setEditForm((prev) => ({ ...prev, name: e.target.value }))} /> : r.name}</td>
              <td>{editingId === r.id ? <input className="input" value={editForm.category} onChange={(e) => setEditForm((prev) => ({ ...prev, category: e.target.value }))} /> : r.category}</td>
              <td>{editingId === r.id ? <input className="input" type="number" min="0" step="0.01" value={editForm.price} onChange={(e) => setEditForm((prev) => ({ ...prev, price: e.target.value }))} /> : `$${Number(r.price || 0).toFixed(2)}`}</td>
              <td>{editingId === r.id ? <input className="input" type="number" min="0" value={editForm.stock} onChange={(e) => setEditForm((prev) => ({ ...prev, stock: e.target.value }))} /> : r.stock}</td>
              <td>
                {editingId === r.id ? (
                  <select className="input" value={editForm.status} onChange={(e) => setEditForm((prev) => ({ ...prev, status: e.target.value }))}>
                    <option>Available</option>
                    <option>Out of Stock</option>
                    <option>Seasonal</option>
                  </select>
                ) : (
                  <StatusPill value={r.status} />
                )}
              </td>
              <td style={{ whiteSpace: "nowrap" }}>
                {editingId === r.id ? (
                  <>
                    <button type="button" className="btn primary" onClick={handleSaveEdit}>Save</button>{" "}
                    <button type="button" className="btn secondary" onClick={() => setEditingId(null)}>Cancel</button>
                  </>
                ) : (
                  <button type="button" className="btn secondary" onClick={() => startEdit(r)}>Edit</button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
