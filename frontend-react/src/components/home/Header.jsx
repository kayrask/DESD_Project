import React, { useState } from "react";
import { Link } from "react-router-dom";

const navItems = [
  { to: "/marketplace", label: "Marketplace" },
  { to: "/for-producers", label: "For Producers" },
  { to: "/how-it-works", label: "How It Works" },
  { to: "/sustainability", label: "Sustainability" },
];

export default function Header() {
  const [open, setOpen] = useState(false);

  return (
    <header className="brfn-header">
      <div className="brfn-header-inner">
        <Link className="brfn-logo" to="/" aria-label="Bristol Regional Food Network home">
          Bristol Regional Food Network
        </Link>

        <nav className="brfn-nav" aria-label="Main navigation">
          {navItems.map((item) => (
            <Link key={item.label} className="brfn-nav-link" to={item.to}>
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="brfn-header-actions">
          <Link className="brfn-btn brfn-btn-secondary" to="/login">Sign In</Link>
          <Link className="brfn-btn brfn-btn-primary" to="/register">Get Started</Link>
          <button
            className="brfn-menu-btn"
            type="button"
            aria-label="Toggle menu"
            aria-expanded={open}
            onClick={() => setOpen((v) => !v)}
          >
            <span />
            <span />
            <span />
          </button>
        </div>
      </div>

      {open ? (
        <nav className="brfn-mobile-nav" aria-label="Mobile navigation">
          {navItems.map((item) => (
            <Link key={item.label} className="brfn-mobile-link" to={item.to} onClick={() => setOpen(false)}>
              {item.label}
            </Link>
          ))}
          <Link className="brfn-btn brfn-btn-primary" to="/register" onClick={() => setOpen(false)}>
            Get Started
          </Link>
        </nav>
      ) : null}
    </header>
  );
}
