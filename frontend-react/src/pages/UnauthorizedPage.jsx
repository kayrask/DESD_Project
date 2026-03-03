import React from "react";
import { Link } from "react-router-dom";

export default function UnauthorizedPage() {
  return (
    <div className="centered">
      <section className="card auth-card">
        <h2>401 Unauthorized</h2>
        <p>You must log in first.</p>
        <Link to="/login">Go to Login</Link>
      </section>
    </div>
  );
}
