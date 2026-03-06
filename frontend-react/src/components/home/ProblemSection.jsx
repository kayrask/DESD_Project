import React from "react";

const cards = [
  {
    title: "Easier local discovery",
    body: "Customers can discover nearby producers and seasonal products without jumping between multiple websites and social feeds.",
  },
  {
    title: "Better producer visibility",
    body: "Producers get a structured storefront with category placement, availability windows, and clear product metadata.",
  },
  {
    title: "Clearer ordering coordination",
    body: "Multi-supplier baskets stay transparent with grouped responsibilities, delivery expectations, and auditable order details.",
  },
];

export default function ProblemSection() {
  return (
    <section className="brfn-problem" id="marketplace" aria-labelledby="problem-title">
      <div className="brfn-section-head">
        <p className="brfn-eyebrow">Why this platform</p>
        <h2 id="problem-title">A single digital layer for Bristol's fragmented local-food ordering flow.</h2>
        <p>
          Customers want local produce without visiting multiple farm shops. Producers need simple listing and order handling.
          Community buyers need one place to source from multiple suppliers. This platform brings those workflows together.
        </p>
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
