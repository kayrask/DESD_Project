from __future__ import annotations

from collections import Counter

from api.models import Product


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


def recommend_products(limit: int = 6, category: str | None = None) -> dict:
    """
    Baseline recommendation engine for Advanced AI sprint evidence.
    Scores in-stock products using category popularity + stock + price.
    """
    all_products = list(Product.objects.all().order_by("id"))

    if not all_products:
        return {"items": [], "model_version": "baseline-v1"}

    category_counts = Counter(p.category.strip() for p in all_products)

    if category:
        candidates = [p for p in all_products if p.category.lower() == category.lower()]
        if not candidates:
            candidates = all_products
    else:
        candidates = all_products

    scored = []
    for product in candidates:
        stock = _safe_int(product.stock)
        price = _safe_float(product.price)

        stock_score = min(stock, 100) / 20.0
        category_score = category_counts.get(product.category.strip(), 0) * 0.15
        price_score = max(0.0, 6.0 - min(price, 12.0))
        status_bonus = 1.0 if product.status.lower() == "available" else -1.0

        score = stock_score + category_score + price_score + status_bonus
        scored.append((score, product))

    top = sorted(scored, key=lambda item: item[0], reverse=True)[: max(1, min(limit, 20))]
    items = [
        {
            "id": product.id,
            "name": product.name,
            "category": product.category,
            "price": _safe_float(product.price),
            "stock": _safe_int(product.stock),
            "status": product.status,
            "producer_id": product.producer_id,
            "score": round(score, 3),
        }
        for score, product in top
    ]
    return {"items": items, "model_version": "baseline-v1"}
