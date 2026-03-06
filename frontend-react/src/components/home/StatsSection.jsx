import React from "react";

const cards = [
  { title: "One checkout across suppliers", sub: "Single flow, multiple producers." },
  { title: "48h lead-time support", sub: "Built for real local fulfilment." },
  { title: "Seasonal visibility", sub: "Availability shown up front." },
  { title: "Clear 5% network fee", sub: "Simple and transparent pricing." },
];

export default function StatsSection() {
  return (
    <section className="brfn-stats" aria-labelledby="stats-title">
      <div className="brfn-section-head">
        <h2 id="stats-title">Built for local food, not generic ecommerce.</h2>
      </div>
      <div className="brfn-stats-grid">
        {cards.map((item) => (
          <article key={item.title} className="brfn-stat-card">
            <h3>{item.title}</h3>
            <p>{item.sub}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
