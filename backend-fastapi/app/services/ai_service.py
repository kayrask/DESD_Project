from __future__ import annotations

from collections import Counter

from app.supabase_client import get_supabase


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
    Current logic: score in-stock products using category popularity + stock + price.
    """
    client = get_supabase()
    rows = (
        client.table("products")
        .select("id,name,category,price,stock,status,producer_id")
        .order("id")
        .execute()
        .data
        or []
    )

    if not rows:
        return {"items": [], "model_version": "baseline-v1"}

    category_counts = Counter(str(row.get("category", "")).strip() for row in rows)
    filtered = [row for row in rows if not category or str(row.get("category", "")).lower() == category.lower()]
    candidates = filtered if filtered else rows

    scored = []
    for row in candidates:
        stock = _safe_int(row.get("stock"))
        price = _safe_float(row.get("price"))
        row_category = str(row.get("category", "")).strip()

        # Higher score for in-stock, popular categories, and accessible price.
        stock_score = min(stock, 100) / 20.0
        category_score = category_counts.get(row_category, 0) * 0.15
        price_score = max(0.0, 6.0 - min(price, 12.0))
        status_bonus = 1.0 if str(row.get("status", "")).lower() == "available" else -1.0

        score = stock_score + category_score + price_score + status_bonus
        scored.append((score, row))

    top = sorted(scored, key=lambda item: item[0], reverse=True)[: max(1, min(limit, 20))]
    items = [
        {
            "id": row.get("id"),
            "name": row.get("name"),
            "category": row.get("category"),
            "price": _safe_float(row.get("price")),
            "stock": _safe_int(row.get("stock")),
            "status": row.get("status"),
            "producer_id": row.get("producer_id"),
            "score": round(score, 3),
        }
        for score, row in top
    ]
    return {"items": items, "model_version": "baseline-v1"}
