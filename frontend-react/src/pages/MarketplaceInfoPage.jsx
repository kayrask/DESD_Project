import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import Header from "../components/home/Header.jsx";
import Footer from "../components/home/Footer.jsx";
import { getRecommendations } from "../api/ai.js";
import { getApiMessage } from "../api/client.js";
import { getCustomerSummary } from "../api/dashboards.js";
import Toast from "../components/Toast.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import StatusPill from "../components/StatusPill.jsx";
import { mockProducts } from "../data/products.js";
import "../styles/homepage.css";

const categories = ["Vegetables", "Fruit", "Dairy", "Bakery", "Pantry"];
const fallbackFeatured = [
  { name: "Heirloom Tomatoes", supplier: "North Farm" },
  { name: "Bristol Apples", supplier: "Valley Orchard" },
  { name: "Farm Eggs", supplier: "River Dairy" },
  { name: "Sourdough Loaf", supplier: "Harbour Bakery" },
];

export default function MarketplaceInfoPage() {
  const { user, token } = useAuth();
  const isCustomer = user?.role === "customer";
  const browseTarget = isCustomer ? "#browse-products" : "/login";
  const [featured, setFeatured] = useState(fallbackFeatured);
  const [summary, setSummary] = useState(null);
  const [summaryError, setSummaryError] = useState("");
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("all");
  const [actionToast, setActionToast] = useState("");

  const categories = useMemo(
    () => Array.from(new Set(mockProducts.map((p) => p.category))),
    [],
  );
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return mockProducts.filter((p) => {
      const matchesQuery =
        !q ||
        p.name.toLowerCase().includes(q) ||
        p.category.toLowerCase().includes(q);
      const matchesCategory = category === "all" || p.category === category;
      return matchesQuery && matchesCategory;
    });
  }, [query, category]);

  useEffect(() => {
    let isMounted = true;

    async function loadRecommendations() {
      try {
        const items = await getRecommendations({ limit: 4 });
        if (!isMounted || !items.length) return;
        setFeatured(
          items.map((item) => ({
            name: item.name,
            supplier: item.category || "Local Supplier",
          })),
        );
      } catch {
        // Keep fallback featured products if API is unavailable.
      }
    }

    loadRecommendations();
    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    let isMounted = true;

    async function loadCustomerSummary() {
      if (!isCustomer || !token) {
        setSummary(null);
        setSummaryError("");
        return;
      }
      const response = await getCustomerSummary(token);
      if (!isMounted) return;
      if (!response.ok) {
        setSummary(null);
        setSummaryError(getApiMessage(response.data, "Failed to load marketplace summary"));
        return;
      }
      setSummary(response.data || null);
      setSummaryError("");
    }

    loadCustomerSummary();
    return () => {
      isMounted = false;
    };
  }, [isCustomer, token]);

  return (
    <div className="brfn-home">
      <Header />
      <main className="brfn-main">
        <section className="brfn-page-intro">
          <p className="brfn-eyebrow">Marketplace</p>
          <h1>Discover local produce across Bristol.</h1>
          <p>Browse by category, search quickly, and order with confidence.</p>
          <div className="brfn-hero-cta">
            {isCustomer ? (
              <a className="brfn-btn brfn-btn-primary" href={browseTarget}>
                Browse Products
              </a>
            ) : (
              <Link className="brfn-btn brfn-btn-primary" to={browseTarget}>
                Browse Products
              </Link>
            )}
            <Link className="brfn-btn brfn-btn-secondary" to={isCustomer ? "/cart" : "/login"}>
              {isCustomer ? "Open Cart" : "Sign In"}
            </Link>
          </div>
        </section>

        <section id="browse-products" className="brfn-simple-section">
          <h2>Browse Products</h2>
          <p>
            Explore seasonal produce by category, compare options, and build your basket in one place.
          </p>
          <Toast message={actionToast} tone="info" />
          <div style={{ display: "grid", gap: 10, marginTop: 12 }}>
            <div style={{ display: "grid", gap: 8, gridTemplateColumns: "2fr 1fr" }}>
              <div>
                <label htmlFor="market-search">Search products</label>
                <input
                  id="market-search"
                  className="input"
                  placeholder="Search by name or category..."
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
              </div>
              <div>
                <label htmlFor="market-category">Filter by category</label>
                <select
                  id="market-category"
                  className="input"
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                >
                  <option value="all">All categories</option>
                  {categories.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <p className="note">
              Showing {filtered.length} of {mockProducts.length} products.
            </p>
          </div>
          <div className="grid" style={{ marginTop: 14 }}>
            {filtered.map((product) => (
              <article key={product.id} className="tile">
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <div>
                    <h3>{product.name}</h3>
                    <p className="note">
                      {product.category} · ${product.price.toFixed(2)}
                    </p>
                  </div>
                  <StatusPill value={product.status} />
                </div>
                <p className="note" style={{ marginTop: 8 }}>{product.shortDescription}</p>
                <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
                  <Link
                    className="btn secondary"
                    to={`/products/${product.id}`}
                    style={{ textDecoration: "none", flex: 1, textAlign: "center" }}
                  >
                    View details
                  </Link>
                  {isCustomer ? (
                    <button
                      type="button"
                      className="btn primary"
                      style={{ flex: 1 }}
                      disabled={product.status === "out_of_stock"}
                      onClick={() => {
                        setActionToast(`Added "${product.name}" to cart (demo).`);
                        window.setTimeout(() => setActionToast(""), 2200);
                      }}
                    >
                      {product.status === "out_of_stock" ? "Out of stock" : "Add to cart"}
                    </button>
                  ) : (
                    <Link
                      className="btn primary"
                      to="/login"
                      style={{ textDecoration: "none", flex: 1, textAlign: "center" }}
                    >
                      Sign in to order
                    </Link>
                  )}
                </div>
              </article>
            ))}
          </div>
        </section>

        {isCustomer ? (
          <section className="brfn-simple-section">
            <h2>Your Marketplace</h2>
            <Toast message={summaryError} tone="danger" />
            <div className="brfn-three-grid">
              <article className="brfn-info-card">
                <h3>Upcoming Deliveries</h3>
                <p>{summary?.upcoming_deliveries ?? "-"}</p>
              </article>
              <article className="brfn-info-card">
                <h3>Saved Producers</h3>
                <p>{summary?.saved_producers ?? "-"}</p>
              </article>
              <article className="brfn-info-card">
                <h3>Quick Actions</h3>
                <p>
                  <Link className="inline-link" to="/products">Browse Products</Link> ·{" "}
                  <Link className="inline-link" to="/cart">View Cart</Link>
                </p>
              </article>
            </div>
          </section>
        ) : null}

        <section className="brfn-simple-section">
          <h2>Categories</h2>
          <div className="brfn-chip-grid">
            {categories.map((item) => (
              <span key={item} className="brfn-chip">{item}</span>
            ))}
          </div>
        </section>

        <section className="brfn-simple-section">
          <h2>Recommended Produce</h2>
          <div className="brfn-three-grid">
            {featured.map((item) => (
              <article key={item.name} className="brfn-info-card">
                <h3>{item.name}</h3>
                <p>{item.supplier}</p>
              </article>
            ))}
          </div>
        </section>
      </main>
      <Footer />
    </div>
  );
}
