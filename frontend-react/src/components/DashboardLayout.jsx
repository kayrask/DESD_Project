import React from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import Header from "./home/Header.jsx";
import "../styles/homepage.css";

function linksForRole(role) {
  if (role === "producer") {
    return [
      ["/producer", "Overview"],
      ["/producer/products", "Products"],
      ["/producer/orders", "Orders"],
      ["/producer/payments", "Payments"],
    ];
  }

  if (role === "admin") {
    return [
      ["/admin", "Overview"],
      ["/admin/reports", "Reports"],
      ["/admin/users", "Users"],
      ["/admin/database", "Database"],
    ];
  }

  return [["/customer", "Overview"]];
}

export default function DashboardLayout() {
  const { user } = useAuth();

  return (
    <div className="dashboard-shell">
      <Header />
      <main className="dashboard-main">
        <section className="dashboard-role-nav card">
          <div className="dashboard-role-head">
            <h1>{user.role === "admin" ? "Admin Workspace" : "Producer Workspace"}</h1>
            <p className="role-pill">{user.role.toUpperCase()}</p>
          </div>
          <nav className="dashboard-links" aria-label={`${user.role} dashboard sections`}>
            {linksForRole(user.role).map(([to, label]) => (
              <NavLink key={to} to={to} end={to === `/${user.role}`} className="dashboard-nav-link">
                {label}
              </NavLink>
            ))}
          </nav>
        </section>
        <section className="dashboard-content">
          <Outlet />
        </section>
      </main>
    </div>
  );
}
