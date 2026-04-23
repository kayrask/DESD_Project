"""
Demand forecast service — loads the SARIMA model trained in
ml/forecasting/demand_forecast.ipynb and serves per-product weekly forecasts.

Falls back to a simple 4-week moving average when the model file is absent
(e.g. before the first training run) so the producer dashboard never crashes.

Author: Nazli
"""

from __future__ import annotations

import pathlib
from collections import defaultdict
from datetime import date

import numpy as np

_MODEL_PATH = (
    pathlib.Path(__file__).resolve().parent.parent.parent
    / "ml" / "forecasting" / "demand_model.pkl"
)

_model_cache: dict | None = None   # loaded once, reused across requests


def _load_model() -> dict | None:
    global _model_cache
    if _model_cache is not None:
        return _model_cache
    if not _MODEL_PATH.exists():
        return None
    try:
        import joblib
        _model_cache = joblib.load(_MODEL_PATH)
        return _model_cache
    except Exception:
        return None


def get_demand_forecast(product_id: int, weeks: int = 4) -> dict:
    """
    Forecast weekly demand for a single product.

    Args:
        product_id: DB primary key of the Product.
        weeks:      Number of future weeks to forecast (default 4).

    Returns:
        {
            "product_id": int,
            "forecast_weeks": int,
            "predicted_units": [float, ...],   # length == weeks
            "model": "sarima" | "moving_average",
            "high_demand": bool,
            "confidence": "model" | "heuristic",
        }
    """
    models = _load_model()

    if models and product_id in models:
        return _sarima_forecast(models[product_id], product_id, weeks)

    return _moving_average_forecast(product_id, weeks)


def _sarima_forecast(entry: dict, product_id: int, weeks: int) -> dict:
    """Use the fitted SARIMA model for this product."""
    try:
        fit = entry["model"]
        preds = fit.forecast(steps=weeks)
        predicted = [round(max(0.0, float(p)), 1) for p in preds]
        mean_pred = float(np.mean(predicted))

        # Rough historical mean from last 12 in-sample fitted values
        try:
            history = list(fit.fittedvalues[-12:])
            hist_mean = float(np.mean(history)) if history else mean_pred
        except Exception:
            hist_mean = mean_pred

        high_demand = mean_pred > 1.5 * hist_mean if hist_mean > 0 else False

        return {
            "product_id":      product_id,
            "forecast_weeks":  weeks,
            "predicted_units": predicted,
            "model":           "sarima",
            "high_demand":     high_demand,
            "confidence":      "model",
        }
    except Exception:
        return _moving_average_forecast(product_id, weeks)


def _moving_average_forecast(product_id: int, weeks: int) -> dict:
    """4-week moving average fallback using delivered OrderItems from the DB."""
    try:
        from django.db.models import Sum
        from api.models import OrderItem

        rows = (
            OrderItem.objects
            .filter(order__status="Delivered", product_id=product_id)
            .values("order__delivery_date")
            .annotate(qty=Sum("quantity"))
            .order_by("order__delivery_date")
        )
        weekly: list[float] = [float(r["qty"]) for r in rows[-8:]]
        if len(weekly) >= 1:
            window = weekly[-4:] if len(weekly) >= 4 else weekly
            pred = round(float(np.mean(window)), 1)
        else:
            pred = 0.0
    except Exception:
        pred = 0.0

    return {
        "product_id":      product_id,
        "forecast_weeks":  weeks,
        "predicted_units": [pred] * weeks,
        "model":           "moving_average",
        "high_demand":     False,
        "confidence":      "heuristic",
    }


def get_demand_forecast_dashboard(producer) -> dict:
    """
    Aggregate forecast for all products owned by a producer.
    Used by ProducerDashboardView.

    Returns the same schema as the previous heuristic implementation
    so the template doesn't need changes.
    """
    import json as _json
    from datetime import date
    from api.models import OrderItem, Product

    today = date.today()
    months: list[tuple[int, int]] = []
    y, m = today.year, today.month
    for _ in range(6):
        months.append((y, m))
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    months.reverse()
    month_labels = [date(y, m, 1).strftime("%b") for y, m in months]

    products = list(
        Product.objects.filter(producer=producer).order_by("name").values("id", "name")
    )
    if not products:
        return {"products": [], "labels": month_labels, "top_product": None, "high_demand_alert": None}

    product_ids = [p["id"] for p in products]
    sales_qs = (
        OrderItem.objects
        .filter(order__producer=producer, order__status="Delivered", product_id__in=product_ids)
        .values("product_id", "order__delivery_date__year", "order__delivery_date__month")
        .annotate(total_qty=__import__("django.db.models", fromlist=["Sum"]).Sum("quantity"))
    )
    sales: dict[tuple, int] = defaultdict(int)
    for row in sales_qs:
        key = (row["product_id"], row["order__delivery_date__year"], row["order__delivery_date__month"])
        sales[key] += row["total_qty"]

    result_products = []
    top_forecast = -1.0
    top_product_name = None
    high_demand_product = None

    for p in products:
        pid = p["id"]
        monthly = [sales.get((pid, yr, mo), 0) for yr, mo in months]

        # Get SARIMA forecast for next month (1 week × 4 ≈ 1 month)
        fc = get_demand_forecast(pid, weeks=4)
        forecast_val = round(sum(fc["predicted_units"]), 1)

        mean6 = sum(monthly) / 6 if sum(monthly) > 0 else 0
        high_demand = fc["high_demand"] or (forecast_val > 1.5 * mean6 if mean6 > 0 else False)

        if monthly[-1] > monthly[-2] if monthly[-2] > 0 else False:
            trend_label = "Rising"
        elif monthly[-1] < monthly[-2] if monthly[-2] > 0 else False:
            trend_label = "Falling"
        else:
            trend_label = "Stable"

        result_products.append({
            "name": p["name"],
            "monthly_sales": monthly,
            "forecast": forecast_val,
            "high_demand": high_demand,
            "trend_label": trend_label,
        })

        if forecast_val > top_forecast:
            top_forecast = forecast_val
            top_product_name = p["name"]
        if high_demand and not high_demand_product:
            high_demand_product = p["name"]

    return {
        "labels": month_labels,
        "products": result_products,
        "top_product": top_product_name,
        "high_demand_alert": (
            f"High demand expected for {high_demand_product} next week"
            if high_demand_product else None
        ),
    }
