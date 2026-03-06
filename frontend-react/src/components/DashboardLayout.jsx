import React from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";

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
    ];
  }

  return [["/customer", "Overview"]];
}

export default function DashboardLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <div className="page">
      <aside className="sidebar">
        <h1>DESD Dashboard</h1>
        <p className="role-pill">{user.role.toUpperCase()}</p>
        <nav>
          {linksForRole(user.role).map(([to, label]) => (
            <NavLink key={to} to={to} end={to === `/${user.role}`} className="nav-link">
              {label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <main className="main">
        <header className="topbar">
          <p>{user.email}</p>
          <button
            className="btn secondary"
            onClick={async () => {
              const result = await logout();
              navigate("/login", {
                replace: true,
                state: { message: result.message, tone: "info" },
              });
            }}
          >
            Log out
          </button>
        </header>
        <Outlet />
      </main>
    </div>
  );
}
