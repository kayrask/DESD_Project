import React from "react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getCustomerSummary } from "../api/dashboards";
import { useAuth } from "../context/AuthContext";

export default function CustomerDashboard() {
  const { token } = useAuth();
  const [data, setData] = useState(null);

  useEffect(() => {
    getCustomerSummary(token).then((res) => {
      if (res.ok) setData(res.data);
    });
  }, [token]);

  return (
    <section className="card">
      <h2>Customer Dashboard</h2>
      <p>Upcoming deliveries: {data?.upcoming_deliveries ?? "-"}</p>
      <p>Saved producers: {data?.saved_producers ?? "-"}</p>
      
      <div className="grid" style={{ marginTop: "24px" }}>
        <Link to="/products" className="tile">
          <h3 style={{ margin: "0 0 8px 0", fontSize: "1.1rem" }}>Browse Products</h3>
          <p className="note" style={{ margin: 0 }}>View all available products</p>
        </Link>
        
        <Link to="/cart" className="tile">
          <h3 style={{ margin: "0 0 8px 0", fontSize: "1.1rem" }}>Shopping Cart</h3>
          <p className="note" style={{ margin: 0 }}>View your cart items</p>
        </Link>
      </div>
    </section>
  );
}
