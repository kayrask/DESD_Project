import React from "react";
import { Link } from "react-router-dom";

export default function CTASection() {
  return (
    <section className="brfn-final-cta" aria-labelledby="final-cta-title">
      <h2 id="final-cta-title">Bring local food ordering into one place.</h2>
      <div className="brfn-hero-cta">
        <Link className="brfn-btn brfn-btn-primary" to="/products">Explore Marketplace</Link>
        <a className="brfn-btn brfn-btn-secondary" href="#producers">Join as a Producer</a>
      </div>
    </section>
  );
}
