import React from "react";

const steps = [
  { title: "Browse local produce", body: "Explore fresh, seasonal listings." },
  { title: "Build your basket", body: "Mix products from one or more suppliers." },
  { title: "Choose delivery or collection", body: "Pick the option that fits your order." },
];

export default function HowItWorks() {
  return (
    <section className="brfn-how" id="how-it-works" aria-labelledby="how-title">
      <div className="brfn-section-head">
        <h2 id="how-title">How it works</h2>
      </div>
      <div className="brfn-how-grid">
        {steps.map((step, idx) => (
          <article className="brfn-step" key={step.title}>
            <span>{idx + 1}</span>
            <h3>{step.title}</h3>
            <p>{step.body}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
