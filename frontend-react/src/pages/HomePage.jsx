import React from "react";
import { Link } from "react-router-dom";

export default function HomePage() {
  return (
    <div className="centered">
      <section className="card home-card">
        <h1>DESD Sprint 1 Portal</h1>
        <p className="note">
          Role-based authentication, dashboard shells, and customer-facing browse/checkout demo.
        </p>

        <div className="grid" style={{ marginTop: "12px" }}>
          <article className="tile">
            <h3>Producer</h3>
            <p className="note">Products, orders, and payments routes.</p>
          </article>
          <article className="tile">
            <h3>Admin</h3>
            <p className="note">Reports and users routes with guard checks.</p>
          </article>
          <article className="tile">
            <h3>Customer</h3>
            <p className="note">Separate route to validate role separation.</p>
          </article>
        </div>

        <div style={{ display: "flex", gap: "8px", marginTop: "16px" }}>
          <Link
            className="btn secondary"
            to="/products"
            style={{ display: "inline-block", textDecoration: "none", flex: 1, textAlign: "center" }}
          >
            Browse products
          </Link>
          <Link
            className="btn primary"
            to="/login"
            style={{ display: "inline-block", textDecoration: "none", flex: 1, textAlign: "center" }}
          >
            Go to Login
          </Link>
        </div>
      </section>
    </div>
  );
}
