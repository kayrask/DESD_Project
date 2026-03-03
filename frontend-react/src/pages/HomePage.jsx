import React from "react";
import { Link } from "react-router-dom";

export default function HomePage() {
  return (
    <div className="centered">
      <section className="card home-card">
        <h1>DESD Sprint 1 Portal</h1>
        <p className="note">Role-based authentication and dashboard shell demo.</p>

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

        <Link className="btn primary" to="/login" style={{ display: "inline-block", textDecoration: "none" }}>
          Go to Login
        </Link>
      </section>
    </div>
  );
}
