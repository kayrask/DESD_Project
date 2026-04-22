"""
Reorder prediction service — loads the Logistic Regression model trained in
ml/reorder/reorder_prediction.ipynb and predicts which products a customer
is most likely to reorder in the next 30 days.

Falls back to trending products (no ML) when the model file is absent or the
customer has no order history, so the customer dashboard never crashes.

Author: Nazli
"""

from __future__ import annotations

import pathlib
from datetime import date, timedelta

import numpy as np

_MODEL_PATH = (
    pathlib.Path(__file__).resolve().parent.parent.parent
    / "ml" / "reorder" / "reorder_model.pkl"
)

_artifact_cache: dict | None = None


def _load_artifact() -> dict | None:
    global _artifact_cache
    if _artifact_cache is not None:
        return _artifact_cache
    if not _MODEL_PATH.exists():
        return None
    try:
        import joblib
        _artifact_cache = joblib.load(_MODEL_PATH)
        return _artifact_cache
    except Exception:
        return None


def predict_reorder_items(customer_email: str) -> list[dict]:
    """
    Return top suggested reorder items for a customer, sorted by reorder
    probability (highest first).

    Args:
        customer_email: The customer's email address (used to look up order history).

    Returns:
        List of dicts:
        [
            {
                "product_id":  int,
                "name":        str,
                "price":       float,
                "category":    str,
                "source":      "model" | "trending",
                "reason":      str,
                "probability": float,  # 0–1
            },
            ...
        ]
        Empty list on error or no history (safe fallback).
    """
    artifact = _load_artifact()

    if artifact:
        ml_results = _model_predict(customer_email, artifact)
        if ml_results:
            return ml_results[:5]

    return _trending_fallback()


def _compute_rfm(customer_email: str) -> list[dict]:
    """Compute RFM features per product for this customer from the Django DB."""
    from django.db.models import Sum, Count, Avg
    from api.models import OrderItem

    today = date.today()
    rows = (
        OrderItem.objects
        .filter(order__customer_name=customer_email)
        .select_related("product", "order")
        .values("product__id", "product__name", "product__category",
                "product__price", "order__delivery_date", "quantity", "unit_price")
    )
    if not rows:
        return []

    from collections import defaultdict
    product_orders: dict[int, list] = defaultdict(list)
    product_meta: dict[int, dict] = {}

    for r in rows:
        pid = r["product__id"]
        product_meta[pid] = {
            "name":     r["product__name"],
            "category": r["product__category"],
            "price":    float(r["product__price"]),
        }
        if r["order__delivery_date"]:
            product_orders[pid].append({
                "date":  r["order__delivery_date"],
                "qty":   r["quantity"],
                "spend": float(r["unit_price"]) * r["quantity"],
            })

    features = []
    for pid, orders in product_orders.items():
        if not orders:
            continue
        orders_sorted = sorted(orders, key=lambda x: x["date"])
        last_date     = orders_sorted[-1]["date"]
        recency       = (today - last_date).days
        frequency     = len(orders_sorted)
        monetary      = sum(o["spend"] for o in orders_sorted)
        last_qty      = orders_sorted[-1]["qty"]

        dates = [o["date"] for o in orders_sorted]
        if len(dates) >= 2:
            intervals = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]
            avg_interval = float(np.mean(intervals))
        else:
            avg_interval = 999.0

        features.append({
            "product_id":        pid,
            "recency":           float(recency),
            "frequency":         float(frequency),
            "monetary":          float(monetary),
            "last_qty":          float(last_qty),
            "avg_interval_days": float(avg_interval),
            **product_meta[pid],
        })

    return features


def _model_predict(customer_email: str, artifact: dict) -> list[dict]:
    """Use the trained Logistic Regression pipeline to score each product."""
    try:
        pipeline     = artifact["pipeline"]
        feature_cols = artifact["feature_cols"]

        product_features = _compute_rfm(customer_email)
        if not product_features:
            return []

        X = np.array([[pf[c] for c in feature_cols] for pf in product_features])
        proba = pipeline.predict_proba(X)[:, 1]

        from api.models import Product
        results = []
        for pf, prob in sorted(zip(product_features, proba), key=lambda x: -x[1]):
            if prob < 0.3:
                break
            # Confirm product is still available
            try:
                p = Product.objects.get(id=pf["product_id"], status__in=["Available", "In Season"], stock__gt=0)
            except Product.DoesNotExist:
                continue

            days_since = int(pf["recency"])
            avg_int    = int(pf["avg_interval_days"])
            reason = (
                f"Usually reorders every {avg_int} days — last ordered {days_since} days ago"
                if avg_int < 900
                else f"Ordered {int(pf['frequency'])}× before — due for a restock?"
            )
            results.append({
                "product_id":  p.id,
                "name":        p.name,
                "price":       float(p.price),
                "category":    p.category,
                "source":      "model",
                "reason":      reason,
                "probability": round(float(prob), 3),
            })

        return results
    except Exception:
        return []


def _trending_fallback() -> list[dict]:
    """Top 3 most-sold products in last 30 days — used when model or history unavailable."""
    try:
        from django.db.models import Sum
        from api.models import OrderItem, Product

        cutoff = date.today() - timedelta(days=30)
        trending = (
            OrderItem.objects
            .filter(order__status="Delivered", order__delivery_date__gte=cutoff)
            .values("product_id")
            .annotate(total=Sum("quantity"))
            .order_by("-total")[:6]
        )
        product_ids = [r["product_id"] for r in trending]
        products = {
            p.id: p
            for p in Product.objects.filter(
                id__in=product_ids, status__in=["Available", "In Season"], stock__gt=0
            )
        }
        results = []
        for r in trending:
            pid = r["product_id"]
            if pid not in products or len(results) >= 3:
                break
            p = products[pid]
            results.append({
                "product_id":  p.id,
                "name":        p.name,
                "price":       float(p.price),
                "category":    p.category,
                "source":      "trending",
                "reason":      f"Popular this month — {r['total']} units sold",
                "probability": 0.5,
            })
        return results
    except Exception:
        return []
