import React from "react";
import Header from "../components/home/Header.jsx";
import Footer from "../components/home/Footer.jsx";
import "../styles/homepage.css";

const points = [
  { title: "Local supply chains", body: "Support producers within the Bristol regional network." },
  { title: "Seasonal buying", body: "Make it easier to choose produce at the right time of year." },
  { title: "Lower food miles", body: "Improve visibility of nearby options before checkout." },
  { title: "Community benefit", body: "Connect households, cafes, and community buyers with local suppliers." },
];

export default function SustainabilityPage() {
  return (
    <div className="brfn-home">
      <Header />
      <main className="brfn-main">
        <section className="brfn-page-intro" id="sustainability">
          <p className="brfn-eyebrow">Sustainability & About</p>
          <h1>Built for Bristol's local food ecosystem.</h1>
          <p>Seasonal, regional, and community-focused by design.</p>
        </section>

        <section className="brfn-simple-section">
          <div className="brfn-three-grid">
            {points.map((item) => (
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
