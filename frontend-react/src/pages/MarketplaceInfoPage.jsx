import React from "react";
import { Link } from "react-router-dom";
import Header from "../components/home/Header.jsx";
import Footer from "../components/home/Footer.jsx";
import "../styles/homepage.css";

const categories = ["Vegetables", "Fruit", "Dairy", "Bakery", "Pantry"];
const featured = [
  { name: "Heirloom Tomatoes", supplier: "North Farm" },
  { name: "Bristol Apples", supplier: "Valley Orchard" },
  { name: "Farm Eggs", supplier: "River Dairy" },
  { name: "Sourdough Loaf", supplier: "Harbour Bakery" },
];

export default function MarketplaceInfoPage() {
  return (
    <div className="brfn-home">
      <Header />
      <main className="brfn-main">
        <section className="brfn-page-intro">
          <p className="brfn-eyebrow">Marketplace</p>
          <h1>Discover local produce across Bristol.</h1>
          <p>Browse by category, search quickly, and order with confidence.</p>
          <div className="brfn-hero-cta">
            <Link className="brfn-btn brfn-btn-primary" to="/products">Start Browsing</Link>
            <Link className="brfn-btn brfn-btn-secondary" to="/login">Sign In</Link>
          </div>
        </section>

        <section className="brfn-simple-section">
          <h2>Categories</h2>
          <div className="brfn-chip-grid">
            {categories.map((item) => (
              <span key={item} className="brfn-chip">{item}</span>
            ))}
          </div>
        </section>

        <section className="brfn-simple-section">
          <h2>Featured Produce</h2>
          <div className="brfn-three-grid">
            {featured.map((item) => (
              <article key={item.name} className="brfn-info-card">
                <h3>{item.name}</h3>
                <p>{item.supplier}</p>
              </article>
            ))}
          </div>
        </section>
      </main>
      <Footer />
    </div>
  );
}
