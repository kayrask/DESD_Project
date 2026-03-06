import React, { useState } from "react";
import Toast from "../components/Toast.jsx";

export default function CheckoutPage() {
  const [form, setForm] = useState({
    fullName: "",
    email: "",
    address: "",
    city: "",
    postalCode: "",
    paymentMethod: "card",
    acceptTerms: false,
  });
  const [errors, setErrors] = useState({});
  const [submitted, setSubmitted] = useState(false);
  const [toast, setToast] = useState({ message: "", tone: "info" });

  function handleChange(event) {
    const { name, value, type, checked } = event.target;
    setForm((prev) => ({
      ...prev,
      [name]: type === "checkbox" ? checked : value,
    }));
  }

  function validate() {
    const nextErrors = {};

    if (!form.fullName.trim()) {
      nextErrors.fullName = "Full name is required.";
    }
    if (!form.email.trim()) {
      nextErrors.email = "Email is required.";
    } else if (!/\S+@\S+\.\S+/.test(form.email)) {
      nextErrors.email = "Enter a valid email address.";
    }
    if (!form.address.trim()) {
      nextErrors.address = "Delivery address is required.";
    }
    if (!form.city.trim()) {
      nextErrors.city = "City is required.";
    }
    if (!form.postalCode.trim()) {
      nextErrors.postalCode = "Postal code is required.";
    } else if (!/^[0-9]{4,10}$/.test(form.postalCode)) {
      nextErrors.postalCode = "Postal code should be 4–10 digits.";
    }
    if (!form.acceptTerms) {
      nextErrors.acceptTerms = "You must confirm the demo terms.";
    }

    return nextErrors;
  }

  function handleSubmit(event) {
    event.preventDefault();
    const nextErrors = validate();
    setErrors(nextErrors);

    if (Object.keys(nextErrors).length > 0) {
      setToast({
        message: "Please fix the highlighted fields before continuing.",
        tone: "danger",
      });
      return;
    }

    setSubmitted(true);
    setToast({
      message: "Checkout submitted successfully (demo only, no payment captured).",
      tone: "info",
    });
  }

  return (
    <div className="centered">
      <section className="card home-card">
        <h1>Checkout</h1>
        <p className="note">
          Checkout shell for Sprint 1 with client-side validation and error states.
        </p>

        <Toast message={toast.message} tone={toast.tone} />

        <form onSubmit={handleSubmit} noValidate>
          <label htmlFor="fullName">Full name</label>
          <input
            id="fullName"
            name="fullName"
            className="input"
            value={form.fullName}
            onChange={handleChange}
            required
          />
          {errors.fullName && <p className="error">{errors.fullName}</p>}

          <label htmlFor="email">Email</label>
          <input
            id="email"
            name="email"
            type="email"
            className="input"
            value={form.email}
            onChange={handleChange}
            required
          />
          {errors.email && <p className="error">{errors.email}</p>}

          <label htmlFor="address">Delivery address</label>
          <input
            id="address"
            name="address"
            className="input"
            value={form.address}
            onChange={handleChange}
            required
          />
          {errors.address && <p className="error">{errors.address}</p>}

          <label htmlFor="city">City</label>
          <input
            id="city"
            name="city"
            className="input"
            value={form.city}
            onChange={handleChange}
            required
          />
          {errors.city && <p className="error">{errors.city}</p>}

          <label htmlFor="postalCode">Postal code</label>
          <input
            id="postalCode"
            name="postalCode"
            className="input"
            value={form.postalCode}
            onChange={handleChange}
            required
          />
          {errors.postalCode && <p className="error">{errors.postalCode}</p>}

          <label htmlFor="paymentMethod">Payment method</label>
          <select
            id="paymentMethod"
            name="paymentMethod"
            className="input"
            value={form.paymentMethod}
            onChange={handleChange}
          >
            <option value="card">Card (demo)</option>
            <option value="bank">Bank transfer (demo)</option>
            <option value="cash">Cash on delivery (demo)</option>
          </select>

          <div style={{ marginTop: "10px" }}>
            <label>
              <input
                type="checkbox"
                name="acceptTerms"
                checked={form.acceptTerms}
                onChange={handleChange}
              />{" "}
              I understand this is a Sprint 1 demo and no real order will be placed.
            </label>
            {errors.acceptTerms && <p className="error">{errors.acceptTerms}</p>}
          </div>

          <button
            type="submit"
            className="btn primary"
            style={{ width: "100%" }}
            disabled={submitted}
          >
            {submitted ? "Submitted" : "Place order (demo)"}
          </button>
        </form>
      </section>
    </div>
  );
}

