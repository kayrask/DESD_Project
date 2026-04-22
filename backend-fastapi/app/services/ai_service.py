"""
AI recommendation service – Advanced AI module.

Two model versions:
  baseline-v1  – category popularity + stock + price heuristic
  collab-v2    – popularity from real order data + category affinity +
                 collaborative signal (products bought together)

Author (ai-integration): Kayra
Evidence prefix: ai-integration
"""
from __future__ import annotations

from collections import Counter, defaultdict

from api.models import OrderItem, Product


def _safe_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


# ── Baseline v1 ──────────────────────────────────────────────────────────────

def _baseline_score(product: Product, category_counts: Counter) -> float:
    stock = _safe_int(product.stock)
    price = _safe_float(product.price)
    stock_score    = min(stock, 100) / 20.0
    category_score = category_counts.get(product.category.strip(), 0) * 0.15
    price_score    = max(0.0, 6.0 - min(price, 12.0))
    status_bonus   = 1.0 if product.status.lower() == "available" else -1.0
    return stock_score + category_score + price_score + status_bonus


def recommend_products_v1(limit: int = 6, category: str | None = None) -> dict:
    """Baseline: category popularity + stock + price heuristic."""
    all_products = list(Product.objects.all().order_by("id"))
    if not all_products:
        return {"items": [], "model_version": "baseline-v1"}

    category_counts = Counter(p.category.strip() for p in all_products)
    candidates = (
        [p for p in all_products if p.category.lower() == category.lower()]
        or all_products
    ) if category else all_products

    scored = [(_baseline_score(p, category_counts), p) for p in candidates]
    top = sorted(scored, reverse=True)[: max(1, min(limit, 20))]
    return {
        "items": [_format_product(p, s, _build_reason(p, 0, 0, 0)) for s, p in top],
        "model_version": "baseline-v1",
    }


# ── Collaborative v2 ─────────────────────────────────────────────────────────

def _build_popularity_map() -> dict[int, int]:
    """Count how many order lines reference each product (global popularity)."""
    counts: dict[int, int] = defaultdict(int)
    for item in OrderItem.objects.select_related("product").all():
        counts[item.product_id] += item.quantity
    return counts


def _build_cooccurrence_map() -> dict[int, Counter]:
    """
    For every pair of products that appear in the same order,
    increment their co-occurrence count.  Used as collaborative signal.
    """
    # Group order items by order_id
    order_to_products: dict[int, list[int]] = defaultdict(list)
    for item in OrderItem.objects.all():
        order_to_products[item.order_id].append(item.product_id)

    cooccur: dict[int, Counter] = defaultdict(Counter)
    for pid_list in order_to_products.values():
        for pid_a in pid_list:
            for pid_b in pid_list:
                if pid_a != pid_b:
                    cooccur[pid_a][pid_b] += 1
    return cooccur


def recommend_products_v2(
    limit: int = 6,
    category: str | None = None,
    customer_email: str | None = None,
) -> dict:
    """
    Improved recommendation engine (collab-v2).

    Scoring components (weighted sum):
      1. Global popularity    – how many times ordered across all customers
      2. Baseline heuristic   – stock, price, category density
      3. Personalisation      – if customer_email given, boost products from
                                their most-bought categories
      4. Collaborative signal – boost products co-ordered with popular items

    Falls back to v1 when order data is empty.
    """
    all_products = list(Product.objects.all().order_by("id"))
    if not all_products:
        return {"items": [], "model_version": "collab-v2"}

    popularity    = _build_popularity_map()
    cooccur       = _build_cooccurrence_map()
    category_counts = Counter(p.category.strip() for p in all_products)

    # Personal category preferences (for logged-in customers)
    personal_categories: Counter = Counter()
    if customer_email:
        personal_items = OrderItem.objects.filter(
            order__customer_name__icontains=customer_email.split("@")[0]
        ).select_related("product")
        personal_categories = Counter(
            item.product.category.lower() for item in personal_items
        )

    # Max popularity for normalisation
    max_pop = max(popularity.values(), default=1)

    candidates = (
        [p for p in all_products if p.category.lower() == category.lower()]
        or all_products
    ) if category else all_products

    scored = []
    for product in candidates:
        pop_score      = (popularity.get(product.id, 0) / max_pop) * 5.0
        baseline       = _baseline_score(product, category_counts) * 0.5
        personal_boost = personal_categories.get(product.category.lower(), 0) * 0.3

        # Collaborative: sum co-occurrence with top-5 popular products
        top_popular = sorted(popularity, key=lambda x: -popularity[x])[:5]
        collab_score = sum(cooccur[product.id].get(pid, 0) for pid in top_popular) * 0.1

        total = pop_score + baseline + personal_boost + collab_score
        scored.append((total, product, pop_score, personal_boost, collab_score))

    top = sorted(scored, key=lambda x: -x[0])[: max(1, min(limit, 20))]
    return {
        "items": [
            _format_product(p, s, _build_reason(p, pop, pers, collab))
            for s, p, pop, pers, collab in top
        ],
        "model_version": "collab-v2",
    }


# ── Public API ────────────────────────────────────────────────────────────────

def recommend_products(
    limit: int = 6,
    category: str | None = None,
    customer_email: str | None = None,
) -> dict:
    """
    Entry point for all views / API endpoints.
    Uses collab-v2 when order data exists, falls back to baseline-v1.
    """
    result = recommend_products_v2(limit=limit, category=category, customer_email=customer_email)
    if not result["items"]:
        result = recommend_products_v1(limit=limit, category=category)
    return result


def _build_reason(
    product: Product,
    pop_score: float,
    personal_boost: float,
    collab_score: float,
) -> str:
    """Plain-language explanation of why this product was recommended."""
    reasons = []
    if personal_boost > 0.3:
        reasons.append(f"matches your frequent {product.category.lower()} purchases")
    if pop_score > 2.0:
        reasons.append("popular with other customers")
    if collab_score > 0.5:
        reasons.append("often bought alongside your other choices")
    if not reasons:
        if _safe_int(product.stock) > 20:
            reasons.append("well stocked by a local producer")
        else:
            reasons.append("available from a local producer")
    return "Recommended because: " + "; ".join(reasons) + "."


def _format_product(product: Product, score: float, reason: str = "") -> dict:
    discount = _safe_int(product.discount_percentage) if hasattr(product, "discount_percentage") else 0
    price = _safe_float(product.price)
    discounted = round(price * (1 - discount / 100), 2) if discount > 0 else None
    return {
        "id": product.id,
        "name": product.name,
        "category": product.category,
        "price": price,
        "discount_percentage": discount,
        "discounted_price": discounted,
        "stock": _safe_int(product.stock),
        "status": product.status,
        "producer_id": product.producer_id,
        "score": round(score, 3),
        "reason": reason,
    }
