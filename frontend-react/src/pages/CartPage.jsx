import React from "react";
import { Link } from "react-router-dom";

export default function CartPage() {
  const demoItems = [
    { id: "eggs-001", name: "Free-range Eggs (12-pack)", quantity: 1, price: 4.5 },
    { id: "milk-002", name: "Organic Whole Milk (1L)", quantity: 2, price: 2.9 },
  ];

  const total = demoItems.reduce((sum, item) => sum + item.quantity * item.price, 0);

  return (
    <div className="centered">
      <section className="card home-card">
        <h1>Your Cart</h1>
        <p className="note">
          Cart shell for Sprint 1 demo. Items are static and not persisted.
        </p>

        <table style={{ marginTop: "16px" }}>
          <thead>
            <tr>
              <th>Product</th>
              <th>Qty</th>
              <th>Price</th>
              <th>Line total</th>
            </tr>
          </thead>
          <tbody>
            {demoItems.map((item) => (
              <tr key={item.id}>
                <td>{item.name}</td>
                <td>{item.quantity}</td>
                <td>${item.price.toFixed(2)}</td>
                <td>${(item.quantity * item.price).toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <th colSpan={3} style={{ textAlign: "right" }}>
                Total
              </th>
              <th>${total.toFixed(2)}</th>
            </tr>
          </tfoot>
        </table>

        <div style={{ display: "flex", gap: "8px", marginTop: "20px" }}>
          <Link
            to="/products"
            className="btn secondary"
            style={{ textDecoration: "none", flex: 1, textAlign: "center" }}
          >
            Continue shopping
          </Link>
          <Link
            to="/checkout"
            className="btn primary"
            style={{ textDecoration: "none", flex: 1, textAlign: "center" }}
          >
            Go to checkout
          </Link>
        </div>
      </section>
    </div>
  );
}

