import React from "react";

const cards = [
  { title: "Discover nearby produce", body: "Find seasonal food from trusted Bristol suppliers." },
  { title: "Order from multiple suppliers", body: "Build one basket across one or many producers." },
  { title: "Track and reorder easily", body: "View order history and repeat regular buys quickly." },
];

export default function CustomerFeatures() {
  return (
    <section className="brfn-benefits" aria-labelledby="customer-title">
      <div className="brfn-section-head">
        <h2 id="customer-title">Everything you need to buy local, in one place.</h2>
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
