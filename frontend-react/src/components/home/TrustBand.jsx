import React from "react";

const items = ["Local Producers", "Independent Cafes", "Community Buyers", "Seasonal Suppliers"];

export default function TrustBand() {
  return (
    <section className="brfn-trust-band" aria-label="Ecosystem trust band">
      {items.map((item) => (
        <span key={item}>{item}</span>
      ))}
    </section>
  );
}
