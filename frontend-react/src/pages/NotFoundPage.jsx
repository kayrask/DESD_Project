import React from "react";
import { Link } from "react-router-dom";

export default function NotFoundPage() {
  return (
    <div className="centered">
      <section className="card auth-card">
        <h2>404 Not Found</h2>
        <Link to="/">Go Home</Link>
      </section>
    </div>
  );
}
