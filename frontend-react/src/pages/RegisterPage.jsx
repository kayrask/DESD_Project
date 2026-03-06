import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { registerRequest } from "../api/auth.js";
import Toast from "../components/Toast.jsx";

export default function RegisterPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    email: "",
    password: "",
    confirmPassword: "",
    fullName: "",
    role: "customer"
  });
  const [error, setError] = useState("");
  const [toast, setToast] = useState({ message: "", tone: "info" });
  const [loading, setLoading] = useState(false);
  const [passwordFocused, setPasswordFocused] = useState(false);

  // Password validation checks
  const passwordChecks = {
    minLength: form.password.length >= 8,
    hasUpper: /[A-Z]/.test(form.password),
    hasLower: /[a-z]/.test(form.password),
    hasNumber: /\d/.test(form.password)
  };

  function handleChange(e) {
    const { name, value } = e.target;
    setForm(prev => ({ ...prev, [name]: value }));
  }

  async function onSubmit(event) {
    event.preventDefault();
    setError("");
    setToast({ message: "", tone: "info" });

    // Validation
    if (form.password !== form.confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    // Validate password strength
    const passwordRegex = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$/;
    if (!passwordRegex.test(form.password)) {
      setError("Password must contain at least 8 characters, including upper, lower, and number.");
      return;
    }

    if (!form.fullName.trim()) {
      setError("Full name is required");
      return;
    }

    setLoading(true);

    try {
      const response = await registerRequest({
        email: form.email.trim(),
        password: form.password,
        full_name: form.fullName.trim(),
        role: form.role
      });

      setToast({
        message: "Registration successful! Redirecting to login...",
        tone: "info"
      });

      // Redirect to login after 2 seconds
      setTimeout(() => {
        navigate("/login");
      }, 2000);

    } catch (err) {
      setError(err.message || "Registration failed. Please try again.");
      setToast({
        message: "Registration failed: " + (err.message || "Unknown error"),
        tone: "danger"
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="centered">
      <section className="card auth-card">
        <h2>Create Account</h2>
        <p className="note">Register as a Customer or Producer</p>

        <Toast message={toast.message} tone={toast.tone} />

        <form onSubmit={onSubmit}>
          <label htmlFor="fullName">Full Name</label>
          <input
            id="fullName"
            name="fullName"
            className="input"
            type="text"
            value={form.fullName}
            onChange={handleChange}
            placeholder="John Doe"
            required
          />

          <label htmlFor="email">Email</label>
          <input
            id="email"
            name="email"
            className="input"
            type="email"
            value={form.email}
            onChange={handleChange}
            placeholder="you@example.com"
            required
          />

          <label htmlFor="password">Password</label>
          <input
            id="password"
            name="password"
            className="input"
            type="password"
            value={form.password}
            onChange={handleChange}
            onFocus={() => setPasswordFocused(true)}
            placeholder="Create a strong password"
            required
          />
          
          {(passwordFocused || form.password) && (
            <div style={{ marginTop: "8px", fontSize: "0.85rem" }}>
              <p style={{ margin: "4px 0", color: passwordChecks.minLength ? "#166534" : "#6b7280" }}>
                {passwordChecks.minLength ? "✓" : "○"} At least 8 characters
              </p>
              <p style={{ margin: "4px 0", color: passwordChecks.hasUpper ? "#166534" : "#6b7280" }}>
                {passwordChecks.hasUpper ? "✓" : "○"} One uppercase letter (A-Z)
              </p>
              <p style={{ margin: "4px 0", color: passwordChecks.hasLower ? "#166534" : "#6b7280" }}>
                {passwordChecks.hasLower ? "✓" : "○"} One lowercase letter (a-z)
              </p>
              <p style={{ margin: "4px 0", color: passwordChecks.hasNumber ? "#166534" : "#6b7280" }}>
                {passwordChecks.hasNumber ? "✓" : "○"} One number (0-9)
              </p>
            </div>
          )}

          <label htmlFor="confirmPassword">Confirm Password</label>
          <input
            id="confirmPassword"
            name="confirmPassword"
            className="input"
            type="password"
            value={form.confirmPassword}
            onChange={handleChange}
            placeholder="Re-enter password"
            required
          />

          <label htmlFor="role">Account Type</label>
          <select
            id="role"
            name="role"
            className="input"
            value={form.role}
            onChange={handleChange}
          >
            <option value="customer">Customer</option>
            <option value="producer">Producer</option>
          </select>

          <button
            className="btn primary"
            type="submit"
            disabled={loading}
            style={{ width: "100%" }}
          >
            {loading ? "Creating Account..." : "Register"}
          </button>

          {error && <p className="error">{error}</p>}
        </form>

        <p className="note" style={{ marginTop: "20px", textAlign: "center" }}>
          Already have an account?{" "}
          <Link to="/login" style={{ color: "var(--primary)", fontWeight: 600 }}>
            Sign in
          </Link>
        </p>
      </section>
    </div>
  );
}
