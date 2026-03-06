import React from "react";
import { Link } from "react-router-dom";

export default function Hero() {
  return (
    <section className="brfn-hero" id="marketplace" aria-labelledby="hero-title">
      <div className="brfn-hero-copy">
        <p className="brfn-eyebrow">Bristol Regional Food Network</p>
        <h1 id="hero-title">Local food, made easier to order.</h1>
        <p>
          Browse seasonal produce from local suppliers across Bristol and place orders in one modern marketplace.
        </p>
        <div className="brfn-hero-cta">
          <Link className="brfn-btn brfn-btn-primary" to="/products">Browse Marketplace</Link>
          <a className="brfn-btn brfn-btn-secondary" href="#producers">For Producers</a>
        </div>
        <ul className="brfn-trust-list" aria-label="Platform proof points">
          <li>Seasonal produce</li>
          <li>Multi-producer checkout</li>
          <li>Transparent ordering</li>
          <li>Local suppliers</li>
        </ul>
      </div>

      <div className="brfn-hero-mockups" aria-hidden="true">
        <article className="mockup-card mockup-market">
          <h3>Marketplace</h3>
          <p>Vegetables, fruit, dairy, bakery</p>
          <div className="mini-grid">
            <span>Heirloom Tomatoes</span>
            <span>Bristol Apples</span>
            <span>Farm Eggs</span>
          </div>
        </article>

        <article className="mockup-card mockup-cart">
          <h3>Grouped Cart</h3>
          <div className="line-item"><b>North Farm</b><span>2 items</span></div>
          <div className="line-item"><b>River Dairy</b><span>1 item</span></div>
        </article>

        <article className="mockup-card mockup-producer">
          <h3>Producer Panel</h3>
          <div className="line-item"><b>Incoming Orders</b><span>12</span></div>
          <div className="line-item"><b>Lead Time</b><span>48h</span></div>
        </article>
      </div>
    </section>
  );
}
