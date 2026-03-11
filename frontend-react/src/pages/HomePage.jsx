import React from "react";
import { useLocation } from "react-router-dom";
import Toast from "../components/Toast.jsx";
import Header from "../components/home/Header.jsx";
import Hero from "../components/home/Hero.jsx";
import TrustBand from "../components/home/TrustBand.jsx";
import StatsSection from "../components/home/StatsSection.jsx";
import CustomerFeatures from "../components/home/CustomerFeatures.jsx";
import CTASection from "../components/home/CTASection.jsx";
import Footer from "../components/home/Footer.jsx";
import "../styles/homepage.css";

export default function HomePage() {
  const location = useLocation();
  const feedbackMessage = location.state?.message || "";
  const feedbackTone = location.state?.tone || "info";

  return (
    <div className="brfn-home">
      <Header />
      <main className="brfn-main">
        <Toast message={feedbackMessage} tone={feedbackTone} />
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
