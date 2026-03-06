import React from "react";
import { Link } from "react-router-dom";

export default function Footer() {
  return (
    <footer className="brfn-footer">
      <div className="brfn-footer-inner">
        <p className="brfn-footer-brand">Bristol Regional Food Network</p>
        <nav aria-label="Footer links">
          <Link to="/marketplace">Marketplace</Link>
          <Link to="/for-producers">For Producers</Link>
          <Link to="/how-it-works">How It Works</Link>
          <Link to="/sustainability">Sustainability</Link>
          <Link to="/login">Sign In</Link>
        </nav>
      </div>
      <p className="brfn-copyright">© 2026 Bristol Regional Food Network</p>
    </footer>
  );
}
