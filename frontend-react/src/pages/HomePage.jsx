import React from "react";
import Header from "../components/home/Header.jsx";
import Hero from "../components/home/Hero.jsx";
import TrustBand from "../components/home/TrustBand.jsx";
import StatsSection from "../components/home/StatsSection.jsx";
import CustomerFeatures from "../components/home/CustomerFeatures.jsx";
import CTASection from "../components/home/CTASection.jsx";
import Footer from "../components/home/Footer.jsx";
import "../styles/homepage.css";

export default function HomePage() {
  return (
    <div className="brfn-home">
      <Header />
      <main className="brfn-main">
        <Hero />
        <TrustBand />
        <StatsSection />
        <CustomerFeatures />
        <CTASection />
      </main>
      <Footer />
    </div>
  );
}
