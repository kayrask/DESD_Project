"""
Quality assessment service – integrates the ML inference pipeline with Django ORM.

Flow:
  1. Producer uploads an image via the web form.
  2. Django saves the image to media/quality_checks/.
  3. This service calls ml.inference.classify_image() to get scores.
  4. A QualityAssessment record is created and returned.
  5. Optionally updates the linked Product status.

Responsible AI considerations (Author: Kayra):
  - Model version is stored with every assessment for auditability.
  - Producers can override the AI grade via the 'notes' field.
  - Low-confidence results (<60%) trigger a warning flag.
  - Grade C automatically suggests a discount rather than removal.

Author (ai-integration): Kayra
Evidence prefix: ai-integration
"""

from __future__ import annotations

from api.models import Product, QualityAssessment, User
from ml.inference import classify_image


# Confidence below this threshold triggers a responsible-AI warning.
LOW_CONFIDENCE_THRESHOLD = 0.60


def assess_product_image(
    image_file,
    product_id: int,
    assessed_by: User,
) -> dict:
    """
    Run the AI quality check on an uploaded image file.

    Args:
        image_file:   Django InMemoryUploadedFile from the form.
        product_id:   PK of the product being assessed.
        assessed_by:  The producer User performing the upload.

    Returns:
        dict with assessment result + any responsible-AI warnings.
    """
    product = Product.objects.get(id=product_id, producer=assessed_by)

    # Read bytes for inference (file will be read again by Django when saving)
    image_bytes = image_file.read()
    image_file.seek(0)  # reset so Django can save it to disk

    result = classify_image(image_bytes, explain=True)

    notes = ""
    warnings = []

    if result["model_confidence"] < LOW_CONFIDENCE_THRESHOLD:
        warnings.append(
            f"Low confidence ({result['model_confidence']:.0%}) — manual review recommended."
        )

    if result["grade"] == "C":
        notes = "AI suggests offering this batch at a discount (Grade C quality). 20% discount applied automatically."
        if product.discount_percentage == 0:
            product.discount_percentage = 20
            product.save(update_fields=["discount_percentage"])
    elif result["grade"] == "A":
        notes = "Premium quality confirmed. Eligible for featured listing."
        if product.discount_percentage > 0:
            product.discount_percentage = 0
            product.save(update_fields=["discount_percentage"])

    assessment = QualityAssessment.objects.create(
        product=product,
        assessed_by=assessed_by,
        image=image_file,
        grade=result["grade"],
        color_score=result["color_score"],
        size_score=result["size_score"],
        ripeness_score=result["ripeness_score"],
        model_confidence=result["model_confidence"],
        model_version=result["model_version"],
        is_healthy=result["is_healthy"],
        notes=notes,
    )

    return {
        "assessment_id": assessment.id,
        "product_name": product.name,
        "grade": result["grade"],
        "color_score": result["color_score"],
        "size_score": result["size_score"],
        "ripeness_score": result["ripeness_score"],
        "model_confidence": result["model_confidence"],
        "model_version": result["model_version"],
        "is_healthy": result["is_healthy"],
        "notes": notes,
        "warnings": warnings,
        # XAI fields — populated when explain=True succeeds; None otherwise
        "xai_heatmap": result.get("xai_heatmap"),
        "xai_explanation": result.get("xai_explanation"),
    }


def get_producer_assessments(producer: User) -> list[dict]:
    """Return all assessments for a producer's products, newest first."""
    assessments = (
        QualityAssessment.objects
        .filter(product__producer=producer)
        .select_related("product")
        .order_by("-assessed_at")
    )
    return [
        {
            "id": a.id,
            "product_name": a.product.name,
            "grade": a.grade,
            "color_score": a.color_score,
            "size_score": a.size_score,
            "ripeness_score": a.ripeness_score,
            "model_confidence": a.model_confidence,
            "model_version": a.model_version,
            "is_healthy": a.is_healthy,
            "notes": a.notes,
            "quantity_lost": a.quantity_lost,
            "assessed_at": a.assessed_at,
        }
        for a in assessments
    ]


def get_ai_monitoring_stats() -> dict:
    """
    Admin-facing stats for the AI monitoring dashboard.
    Provides model usage, grade distribution, and confidence summary.
    """
    from django.db.models import Avg, Count

    qs = QualityAssessment.objects.all()
    total = qs.count()

    if total == 0:
        return {
            "total_assessments": 0,
            "grade_distribution": {"A": 0, "B": 0, "C": 0},
            "avg_confidence": 0,
            "low_confidence_count": 0,
            "model_versions": [],
        }

    grade_dist = {
        row["grade"]: row["count"]
        for row in qs.values("grade").annotate(count=Count("id"))
    }
    avg_conf = qs.aggregate(avg=Avg("model_confidence"))["avg"] or 0
    low_conf = qs.filter(model_confidence__lt=LOW_CONFIDENCE_THRESHOLD).count()
    versions = list(qs.values_list("model_version", flat=True).distinct())

    return {
        "total_assessments": total,
        "grade_distribution": {
            "A": grade_dist.get("A", 0),
            "B": grade_dist.get("B", 0),
            "C": grade_dist.get("C", 0),
        },
        "avg_confidence": round(avg_conf * 100, 1),
        "low_confidence_count": low_conf,
        "model_versions": versions,
    }
