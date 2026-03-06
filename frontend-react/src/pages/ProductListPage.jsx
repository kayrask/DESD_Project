import React, { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { mockProducts } from "../data/products.js";
import StatusPill from "../components/StatusPill.jsx";
import Toast from "../components/Toast.jsx";

export default function ProductListPage() {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("all");
  const [toast, setToast] = useState({ message: "", tone: "info" });

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return mockProducts.filter((p) => {
      const matchesQuery =
        !q ||
        p.name.toLowerCase().includes(q) ||
        p.category.toLowerCase().includes(q);
      const matchesCategory = category === "all" || p.category === category;
      return matchesQuery && matchesCategory;
    });
  }, [query, category]);

  function handleAddToCart(product) {
    setToast({
      message: `Added "${product.name}" to cart (demo only).`,
      tone: "info",
    });
    window.setTimeout(() => {
      setToast({ message: "", tone: "info" });
    }, 2500);
  }

  const categories = Array.from(new Set(mockProducts.map((p) => p.category)));

  return (
    <div className="centered">
      <section className="card home-card">
        <h1>Browse Products</h1>
        <p className="note">
          Customer-facing product list shell with search and filters. This uses
          mock data only for Sprint 1.
        </p>

        <Toast message={toast.message} tone={toast.tone} />

        <div style={{ display: "grid", gap: "10px", marginTop: "12px" }}>
          <div style={{ display: "grid", gap: "8px", gridTemplateColumns: "2fr 1fr" }}>
            <div>
              <label htmlFor="search">Search products</label>
              <input
                id="search"
                className="input"
                placeholder="Search by name or category…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>
            <div>
              <label htmlFor="category">Filter by category</label>
              <select
                id="category"
                className="input"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
              >
                <option value="all">All categories</option>
                {categories.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <p className="note">
              Showing {filtered.length} of {mockProducts.length} demo products.
            </p>
            <Link className="btn secondary" to="/cart" style={{ textDecoration: "none" }}>
              Go to Cart
            </Link>
          </div>
        </div>

        <div className="grid" style={{ marginTop: "16px" }}>
          {filtered.map((product) => (
            <article key={product.id} className="tile">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                <div>
                  <h3>{product.name}</h3>
                  <p className="note">
                    {product.category} · ${product.price.toFixed(2)}
                  </p>
                </div>
                <StatusPill value={product.status} />
              </div>
              <p className="note" style={{ marginTop: "8px" }}>
                {product.shortDescription}
              </p>
              <div style={{ display: "flex", gap: "8px", marginTop: "10px" }}>
                <Link
                  to={`/products/${product.id}`}
                  className="btn secondary"
                  style={{ textDecoration: "none", flex: 1, textAlign: "center" }}
                >
                  View details
                </Link>
                <button
                  type="button"
                  className="btn primary"
                  style={{ flex: 1 }}
                  onClick={() => handleAddToCart(product)}
                  disabled={product.status === "out_of_stock"}
                >
                  {product.status === "out_of_stock" ? "Out of stock" : "Add to cart"}
                </button>
              </div>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}

