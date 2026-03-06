import React from "react";

const cards = [
  { title: "Manage listings quickly", body: "Add and update products in a clean dashboard." },
  { title: "Keep stock and seasonality clear", body: "Show what is available and when." },
  { title: "Track incoming orders easily", body: "Move orders through status with less admin." },
];

export default function ProducerFeatures() {
  return (
    <section className="brfn-benefits" id="producers" aria-labelledby="producer-title">
      <div className="brfn-section-head">
        <h2 id="producer-title">A simpler way for producers to sell online.</h2>
      </div>
      <div className="brfn-three-grid">
        {cards.map((card) => (
          <article className="brfn-info-card" key={card.title}>
            <h3>{card.title}</h3>
            <p>{card.body}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
