import React from "react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("producer@desd.local");
  const [password, setPassword] = useState("password123");
  const [error, setError] = useState("");

  async function onSubmit(event) {
    event.preventDefault();
    setError("");

    const result = await login(email.trim(), password);
    if (!result.ok) {
      setError(result.message);
      return;
    }

    if (result.user.role === "producer") navigate("/producer", { replace: true });
    else if (result.user.role === "admin") navigate("/admin", { replace: true });
    else navigate("/customer", { replace: true });
  }

  return (
    <div className="centered">
      <section className="card auth-card">
        <h2>Sign in</h2>
        <p className="note">Sprint 1 auth + role routing demo</p>
        <ul className="note">
          <li>producer@desd.local / password123</li>
          <li>admin@desd.local / password123</li>
          <li>customer@desd.local / password123</li>
        </ul>

        <form onSubmit={onSubmit}>
          <label>Email</label>
          <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />

          <label>Password</label>
          <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />

          <button className="btn primary" type="submit">Login</button>
          {error ? <p className="error">{error}</p> : null}
        </form>
      </section>
    </div>
  );
}
