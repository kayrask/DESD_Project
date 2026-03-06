import React from "react";
import Header from "../components/home/Header.jsx";
import Footer from "../components/home/Footer.jsx";
import "../styles/homepage.css";

const steps = [
  { title: "Discover local produce", body: "Browse suppliers and seasonal products across Bristol." },
  { title: "Build your basket", body: "Add items from one or more producers in one checkout flow." },
  { title: "Choose delivery or collection", body: "See clear fulfilment options and supplier responsibility." },
  { title: "Manage fulfilment", body: "Producers receive, prepare, and update order statuses." },
];

export default function HowItWorksPage() {
  return (
    <div className="brfn-home">
      <Header />
      <main className="brfn-main">
        <section className="brfn-page-intro" id="how-it-works">
          <p className="brfn-eyebrow">How It Works</p>
          <h1>Simple flow. Clear coordination.</h1>
          <p>A straightforward process for customers and producers.</p>
        </section>

        <section className="brfn-simple-section">
          <div className="brfn-how-grid brfn-how-grid-4">
            {steps.map((step, idx) => (
              <article className="brfn-step" key={step.title}>
                <span>{idx + 1}</span>
                <h3>{step.title}</h3>
                <p>{step.body}</p>
              </article>
            ))}
          </div>
        </section>
      </main>
      <Footer />
    </div>
  );
}
