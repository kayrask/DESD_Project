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

from api.models import Product, QualityAssessment, QualityOverride, User
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
        if product.ai_discount_percentage == 0:
            product.ai_discount_percentage = 20
            product.ai_discount_active = True
            product.save(update_fields=["ai_discount_percentage", "ai_discount_active"])
    elif result["grade"] == "A":
        notes = "Premium quality confirmed. Eligible for featured listing."
        if product.ai_discount_active and product.ai_discount_percentage > 0:
            product.ai_discount_percentage = 0
            product.ai_discount_active = False
            product.save(update_fields=["ai_discount_percentage", "ai_discount_active"])

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
        "predicted_class": result.get("predicted_class"),
        "price": float(product.price),
        "discount_percentage": product.discount_percentage,
        "ai_discount_percentage": product.ai_discount_percentage,
        "effective_discount_percentage": product.effective_discount_percentage,
        "discounted_price": product.discounted_price,
        "ai_discount_active": product.ai_discount_active,
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


def _load_training_chart() -> str | None:
    import base64, pathlib
    chart_path = pathlib.Path(__file__).parent.parent.parent / "fruit_quality_ai" / "results" / "training_history.png"
    if chart_path.exists():
        with open(chart_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    return None


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
            "override_count": QualityOverride.objects.count(),
            "training_chart": _load_training_chart(),
        }

    grade_dist = {
        row["grade"]: row["count"]
        for row in qs.values("grade").annotate(count=Count("id"))
    }
    avg_conf = qs.aggregate(avg=Avg("model_confidence"))["avg"] or 0
    low_conf = qs.filter(model_confidence__lt=LOW_CONFIDENCE_THRESHOLD).count()
    versions = list(qs.values_list("model_version", flat=True).distinct())

    override_count = QualityOverride.objects.count()

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
        "override_count": override_count,
        "training_chart": _load_training_chart(),
    }


# ── Model metrics bridge ──────────────────────────────────────────────────────
# The admin AI monitoring page reads a single dict with keys
# {accuracy, precision, recall, f1_score, fairness, ...}. The OLD binary
# evaluator (ml/evaluate.py) already emits that schema to
# ml/saved_models/model_metrics.json. The NEW 28-class evaluator
# (fruit_quality_ai/evaluation/evaluator.py) emits a different shape to
# fruit_quality_ai/results/evaluation_report.json.
#
# load_latest_model_metrics() prefers the new model's report when present and
# normalises it into the legacy schema so the admin page works for both.

def _load_new_model_metrics() -> dict | None:
    """Read fruit_quality_ai/results/evaluation_report.json, normalise it into
    the schema the admin monitoring template expects, and compute per-produce
    fairness (weakest rotten-class recall + healthy/rotten accuracy gap).
    Returns None if the report doesn't exist yet."""
    import json
    import pathlib

    report_path = (
        pathlib.Path(__file__).resolve().parent.parent.parent
        / "fruit_quality_ai" / "results" / "evaluation_report.json"
    )
    if not report_path.exists():
        return None
    try:
        with open(report_path) as f:
            raw = json.load(f)
    except Exception:
        return None

    per_class = raw.get("per_class", {})
    weighted = per_class.get("weighted avg", {}) or per_class.get("macro avg", {})

    # ── Per-produce fairness ──────────────────────────────────────────────────
    # Class names follow "<produce>_<healthy|rotten>_..."
    # Group recalls by produce type and by condition (healthy vs rotten) to
    # surface (a) weakest rotten-recall (food-safety risk) and
    # (b) healthy/rotten recall gap (producer-fairness risk).
    healthy_recalls: list[float] = []
    rotten_recalls: list[float] = []
    weakest_rotten: tuple[str, float] | None = None
    for class_name, stats in per_class.items():
        if class_name in ("accuracy", "macro avg", "weighted avg"):
            continue
        if not isinstance(stats, dict):
            continue
        recall = float(stats.get("recall", 0.0) or 0.0)
        if "_healthy_" in class_name:
            healthy_recalls.append(recall)
        elif "_rotten_" in class_name:
            rotten_recalls.append(recall)
            if weakest_rotten is None or recall < weakest_rotten[1]:
                produce = class_name.split("_", 1)[0]
                weakest_rotten = (produce, recall)

    fairness: dict | None = None
    if healthy_recalls and rotten_recalls:
        mean_healthy = sum(healthy_recalls) / len(healthy_recalls)
        mean_rotten = sum(rotten_recalls) / len(rotten_recalls)
        gap = abs(mean_healthy - mean_rotten)
        # Reuse the legacy schema keys so the existing template card works.
        # fpr_healthy  ≈ 1 - mean_healthy_recall  (rate healthy produce mis-flagged)
        # fnr_rotten   ≈ 1 - mean_rotten_recall   (rate rotten produce missed)
        fairness = {
            "fpr_healthy": round(1.0 - mean_healthy, 4),
            "fnr_rotten":  round(1.0 - mean_rotten, 4),
            "equalized_odds_gap": round(gap, 4),
            "fairness_verdict": (
                "Acceptable (per-class recall gap ≤ 0.10)"
                if gap <= 0.10
                else "Warning: per-class recall gap > 0.10"
            ),
            "weakest_rotten_produce": weakest_rotten[0] if weakest_rotten else None,
            "weakest_rotten_recall": round(weakest_rotten[1], 4) if weakest_rotten else None,
        }

    return {
        "model_version": raw.get("model_version", "efficientnet-b0-v1"),
        "accuracy":      round(float(raw.get("accuracy", 0.0)), 4),
        "precision":     round(float(weighted.get("precision", 0.0) or 0.0), 4),
        "recall":        round(float(weighted.get("recall", 0.0) or 0.0), 4),
        "f1_score":      round(float(weighted.get("f1-score", 0.0) or 0.0), 4),
        "auc_roc":       raw.get("auc_roc"),
        "dataset":       raw.get("dataset", "Fruit & Vegetable Disease (Healthy vs Rotten)"),
        "train_samples": raw.get("train_samples"),
        "val_samples":   raw.get("val_samples"),
        "updated_at":    raw.get("updated_at"),
        "fairness":      fairness,
        "num_classes":   len([k for k in per_class if k not in ("accuracy", "macro avg", "weighted avg")]),
    }


def _load_legacy_model_metrics() -> dict | None:
    """Read the old binary classifier's metrics JSON in its original schema."""
    import json
    import pathlib

    path = (
        pathlib.Path(__file__).resolve().parent.parent.parent
        / "ml" / "saved_models" / "model_metrics.json"
    )
    if not path.exists():
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def load_latest_model_metrics() -> dict | None:
    """Prefer the new 28-class model's metrics when present, else fall back
    to the legacy binary model's metrics. Returns None if neither exists."""
    return _load_new_model_metrics() or _load_legacy_model_metrics()


def find_confusion_matrix_path() -> "pathlib.Path | None":
    """Locate the confusion-matrix image from whichever evaluator wrote one."""
    import pathlib

    backend_root = pathlib.Path(__file__).resolve().parent.parent.parent
    candidates = [
        backend_root / "fruit_quality_ai" / "results" / "confusion_matrix.png",
        backend_root / "ml" / "saved_models" / "confusion_matrix.png",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None
