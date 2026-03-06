import React from "react";
import { Link, useParams } from "react-router-dom";
import { mockProducts } from "../data/products.js";
import StatusPill from "../components/StatusPill.jsx";

export default function ProductDetailPage() {
  const { id } = useParams();
  const product = mockProducts.find((p) => p.id === id);

  if (!product) {
    return (
      <div className="centered">
        <section className="card auth-card">
          <h1>Product not found</h1>
          <p className="note">This demo product ID does not exist.</p>
          <Link className="btn primary" to="/products" style={{ textDecoration: "none" }}>
            Back to products
          </Link>
        </section>
      </div>
    );
  }

  return (
    <div className="centered">
      <section className="card home-card">
        <h1>{product.name}</h1>
        <p className="note">
          {product.category} · ${product.price.toFixed(2)}
        </p>
        <div style={{ marginTop: "8px" }}>
          <StatusPill value={product.status} />
        </div>

        <p style={{ marginTop: "16px" }}>{product.description}</p>

        <div style={{ display: "flex", gap: "8px", marginTop: "20px" }}>
          <Link
            to="/products"
            className="btn secondary"
            style={{ textDecoration: "none", flex: 1, textAlign: "center" }}
          >
            Back to list
          </Link>
          <Link
            to="/cart"
            className="btn primary"
            style={{ textDecoration: "none", flex: 1, textAlign: "center" }}
          >
            Add to cart (demo)
          </Link>
        </div>

        <p className="note" style={{ marginTop: "10px" }}>
          This page is a shell for Sprint 1 to demonstrate navigation from list to detail and into checkout.
        </p>
      </section>
    </div>
  );
}

