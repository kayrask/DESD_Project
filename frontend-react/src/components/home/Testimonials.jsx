import React from "react";

const quotes = [
  {
    role: "Producer",
    text: "I can update seasonal stock quickly and see incoming orders without juggling spreadsheets.",
    person: "Independent Grower, Bristol Fringe",
  },
  {
    role: "Independent Cafe Owner",
    text: "Grouped checkout makes local sourcing practical for weekly purchasing, not just occasional buying.",
    person: "Cafe Owner, Clifton",
  },
  {
    role: "Family Customer",
    text: "We can order from multiple local suppliers in one flow and still see exactly who delivers each item.",
    person: "Household Buyer, North Bristol",
  },
];

export default function Testimonials() {
  return (
    <section className="brfn-testimonials" aria-labelledby="quotes-title">
      <div className="brfn-section-head">
        <p className="brfn-eyebrow">Stakeholder Voices</p>
        <h2 id="quotes-title">Built around real local-food personas.</h2>
      </div>
      <div className="brfn-quote-grid">
        {quotes.map((quote) => (
          <article className="brfn-quote" key={quote.person}>
            <h3>{quote.role}</h3>
            <p>"{quote.text}"</p>
            <small>{quote.person}</small>
          </article>
        ))}
      </div>
    </section>
  );
}
