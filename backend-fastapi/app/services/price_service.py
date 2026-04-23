"""
AI-driven price recommendation service.

Combines quality grade (from QualityAssessment) with the demand forecast
to suggest an optimal price for a product after each quality check.

Rules
-----
Grade A + high demand  → +10% (premium pricing)
Grade A                → no change
Grade B + high demand  → no change (demand compensates standard quality)
Grade B                → no change
Grade C + high demand  → −15% (must move stock despite demand pressure)
Grade C                → −20%

Author: Nazli
"""

from __future__ import annotations


def recommend_price(product, grade: str, high_demand: bool) -> dict:
    """
    Return a price recommendation dict.

    Args:
        product:     Product ORM instance (needs .price).
        grade:       'A' | 'B' | 'C'
        high_demand: bool from forecast_service high_demand flag.

    Returns:
        current_price   float
        suggested_price float
        change_pct      float  (positive = increase, negative = discount)
        reason          str
        action          'increase' | 'hold' | 'discount'
    """
    current = float(product.price)

    if grade == "A" and high_demand:
        factor, reason, action = 1.10, "Premium quality and high demand forecast — consider a 10% price increase.", "increase"
    elif grade == "A":
        factor, reason, action = 1.00, "Premium quality — current price is appropriate.", "hold"
    elif grade == "B" and high_demand:
        factor, reason, action = 1.00, "Standard quality, but strong demand — hold price.", "hold"
    elif grade == "B":
        factor, reason, action = 1.00, "Standard quality — no price change needed.", "hold"
    elif grade == "C" and high_demand:
        factor, reason, action = 0.85, "Below-standard quality — 15% discount recommended to move stock quickly.", "discount"
    else:
        factor, reason, action = 0.80, "Below-standard quality and normal demand — 20% discount recommended.", "discount"

    suggested = round(current * factor, 2)
    change_pct = round((factor - 1) * 100, 1)

    return {
        "current_price":   current,
        "suggested_price": suggested,
        "change_pct":      change_pct,
        "reason":          reason,
        "action":          action,
    }


def get_quality_trend(producer, weeks: int = 8) -> list[dict]:
    """
    Return weekly grade distribution for a producer's products.

    Returns a list of {week, A, B, C} dicts ordered oldest → newest.
    """
    from datetime import date, timedelta
    from django.db.models import Count
    from api.models import QualityAssessment

    today = date.today()
    results = []
    for i in range(weeks - 1, -1, -1):
        week_start = today - timedelta(days=today.weekday() + 7 * i)
        week_end   = week_start + timedelta(days=6)
        qs = QualityAssessment.objects.filter(
            product__producer=producer,
            assessed_at__date__gte=week_start,
            assessed_at__date__lte=week_end,
        )
        grade_counts = {
            row["grade"]: row["count"]
            for row in qs.values("grade").annotate(count=Count("id"))
        }
        results.append({
            "week": week_start.strftime("%d %b"),
            "A":    grade_counts.get("A", 0),
            "B":    grade_counts.get("B", 0),
            "C":    grade_counts.get("C", 0),
        })
    return results
