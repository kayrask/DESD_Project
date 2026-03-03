import React from "react";
import { useEffect, useState } from "react";
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
      <p className="note">Try /producer while logged in as customer to trigger 403.</p>
    </section>
  );
}
