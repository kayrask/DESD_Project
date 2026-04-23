"""
Waste / spoilage risk scoring.

Combines three signals:
  - AI quality grade (from the most recent QualityAssessment)
  - Current stock level
  - 2-week demand forecast (SARIMA or moving-average fallback)

Risk formula (0–100):
  grade_risk  : C=70, B=30, A=0   (40% weight)
  supply_risk : (stock / forecast_2w - 1).clip(0, 1)  (60% weight)

Author: Nazli
"""

from __future__ import annotations


_GRADE_RISK = {"A": 0, "B": 30, "C": 70}
_RISK_LABELS = {
    (0, 30):  ("Low",    "#15803d"),
    (30, 60): ("Medium", "#d97706"),
    (60, 101):("High",   "#dc2626"),
}


def compute_waste_risk(product) -> dict:
    """
    Return a waste risk dict for a single Product instance.

    Keys:
        risk_score        int  0-100
        risk_level        str  'Low' | 'Medium' | 'High'
        risk_colour       str  hex colour for the badge
        grade             str  'A' | 'B' | 'C' | '–'
        stock             int
        predicted_demand_2w  float  sum of 2-week forecast
    """
    from api.models import QualityAssessment
    from app.services.forecast_service import get_demand_forecast

    latest = (
        QualityAssessment.objects
        .filter(product=product)
        .order_by("-assessed_at")
        .values("grade")
        .first()
    )
    grade = latest["grade"] if latest else None
    grade_risk = _GRADE_RISK.get(grade, 30)

    fc = get_demand_forecast(product.id, weeks=2)
    predicted_2w = max(sum(fc["predicted_units"]), 0.5)

    stock = product.stock or 0
    supply_ratio = stock / predicted_2w - 1
    supply_risk = min(max(supply_ratio, 0.0), 1.0)

    raw = grade_risk * 0.4 + supply_risk * 100 * 0.6
    risk_score = round(min(raw, 100))

    risk_level, risk_colour = "Low", "#15803d"
    for (lo, hi), (label, colour) in _RISK_LABELS.items():
        if lo <= risk_score < hi:
            risk_level, risk_colour = label, colour
            break

    return {
        "risk_score":          risk_score,
        "risk_level":          risk_level,
        "risk_colour":         risk_colour,
        "grade":               grade or "–",
        "stock":               stock,
        "predicted_demand_2w": round(predicted_2w, 1),
    }


def get_waste_risks(products) -> dict:
    """Return {product.id: risk_dict} for an iterable of Product objects."""
    results = {}
    for p in products:
        try:
            results[p.id] = compute_waste_risk(p)
        except Exception:
            results[p.id] = None
    return results
