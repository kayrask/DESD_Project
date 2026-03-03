import React from "react";
import { Link } from "react-router-dom";

export default function ForbiddenPage() {
  return (
    <div className="centered">
      <section className="card auth-card">
        <h2>403 Access Denied</h2>
        <p>Your role cannot access this route.</p>
        <Link to="/">Back Home</Link>
      </section>
    </div>
  );
}
