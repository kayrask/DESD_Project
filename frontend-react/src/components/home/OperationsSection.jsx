import React from "react";

export default function OperationsSection() {
  return (
    <section className="brfn-operations" aria-labelledby="operations-title">
      <div className="brfn-section-head">
        <p className="brfn-eyebrow">Transparency & Operations</p>
        <h2 id="operations-title">Operational clarity built into every multi-vendor order.</h2>
      </div>
      <div className="brfn-ops-grid">
        <article className="brfn-info-card">
          <h3>Supplier responsibility visibility</h3>
          <p>Each basket is grouped by producer so customers and admins can see who fulfils each item.</p>
        </article>
        <article className="brfn-info-card">
          <h3>Delivery and collection transparency</h3>
          <p>Collection points, delivery windows, and producer-specific logistics are shown clearly at checkout.</p>
        </article>
        <article className="brfn-info-card">
          <h3>Secure payments and commission logic</h3>
          <p>Payments run in secure test mode while the 5% network commission is calculated consistently.</p>
        </article>
        <article className="brfn-info-card">
          <h3>Audit-ready records</h3>
          <p>Admin reporting and database visibility support operational reviews and accountability.</p>
        </article>
      </div>
    </section>
  );
}
