import React from "react";
import { Link } from "react-router-dom";
import Header from "../components/home/Header.jsx";
import Footer from "../components/home/Footer.jsx";
import "../styles/homepage.css";

const sections = [
  {
    title: "Why sell through the platform",
    body: "Reach local customers in one marketplace built for seasonal food.",
  },
  {
    title: "Manage products and seasonality",
    body: "Update listings, stock, and availability windows in minutes.",
  },
  {
    title: "Track incoming orders",
    body: "See new orders clearly and prepare with a 48-hour lead-time rule.",
  },
  {
    title: "Fulfilment workflow",
    body: "Move orders through clear status steps from pending to delivered.",
  },
  {
    title: "Transparent operations",
    body: "View supplier responsibilities and a clear 5% network commission model.",
  },
  {
    title: "Producer dashboard preview",
    body: "Use one simple workspace for products, orders, and delivery coordination.",
  },
];

export default function ForProducersPage() {
  return (
    <div className="brfn-home">
      <Header />
      <main className="brfn-main">
        <section className="brfn-page-intro" id="producers">
          <p className="brfn-eyebrow">For Producers</p>
          <h1>A simpler way to sell local food online.</h1>
          <p>Everything you need to list products, manage stock, and handle orders.</p>
          <div className="brfn-hero-cta">
            <Link className="brfn-btn brfn-btn-primary" to="/login">Join as a Producer</Link>
            <Link className="brfn-btn brfn-btn-secondary" to="/how-it-works">See Workflow</Link>
          </div>
        </section>

        <section className="brfn-simple-section">
          <div className="brfn-three-grid">
            {sections.map((item) => (
              <article key={item.title} className="brfn-info-card">
                <h3>{item.title}</h3>
                <p>{item.body}</p>
              </article>
            ))}
          </div>
        </section>
      </main>
      <Footer />
    </div>
  );
}
