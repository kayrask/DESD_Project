import pathlib

from celery import shared_task
from django.utils import timezone
from datetime import timedelta

_BACKEND_ROOT = pathlib.Path(__file__).resolve().parent.parent
_DATASET_PATH = _BACKEND_ROOT / "ml" / "Fruit And Vegetable Diseases Dataset"
_METRICS_PATH = _BACKEND_ROOT / "ml" / "saved_models" / "model_metrics.json"


@shared_task(max_retries=0)
def evaluate_model_after_upload(model_version: str, arch: str = "mobilenetv2"):
    """Run the correct evaluator for the uploaded model, in a subprocess.

    Architectures:
      - "efficientnet-b0" → fruit_quality_ai/main.py --mode evaluate
                            (writes fruit_quality_ai/results/evaluation_report.json)
      - "mobilenetv2"     → ml.evaluate
                            (writes ml/saved_models/model_metrics.json)

    Subprocess isolation keeps PyTorch memory separate from the Celery worker
    so two concurrent uploads can't OOM each other. After evaluation succeeds
    we write a ModelEvaluation row so the admin accuracy-over-time chart
    tracks the new version alongside the older ones.
    """
    import json
    import subprocess
    import sys

    if arch.startswith("efficientnet"):
        cmd = [sys.executable, "fruit_quality_ai/main.py", "--mode", "evaluate"]
    else:
        cmd = [
            sys.executable, "-m", "ml.evaluate",
            "--data_dir", str(_DATASET_PATH),
            "--model_version", model_version,
        ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(_BACKEND_ROOT),
    )
    if result.returncode != 0:
        raise RuntimeError(f"Evaluation ({arch}) failed:\n{result.stderr}")

    # Use the same bridge the admin page reads so we record the exact metrics
    # that will appear in the UI. Handles both schemas (new 28-class + legacy).
    from app.services.quality_service import load_latest_model_metrics
    m = load_latest_model_metrics()
    if m:
        from api.models import ModelEvaluation
        ModelEvaluation.objects.create(
            version=m.get("model_version", model_version),
            accuracy=m.get("accuracy", 0.0),
            precision=m.get("precision", 0.0),
            recall=m.get("recall", 0.0),
            f1_score=m.get("f1_score", 0.0),
        )

    return f"Evaluation complete for {model_version}"


@shared_task
def cleanup_stale_reservations():
    """Remove CartReservations older than 2 hours (abandoned carts)."""
    from api.models import CartReservation
    cutoff = timezone.now() - timedelta(hours=2)
    deleted, _ = CartReservation.objects.filter(updated_at__lt=cutoff).delete()
    return f"Deleted {deleted} stale cart reservations"


@shared_task
def expire_pending_orders():
    """
    Cancel vendor Orders that have passed their expires_at deadline
    without being confirmed by the producer.
    Only Pending orders are expired — once confirmed/ready/delivered they
    are no longer cancellable by this task.
    """
    from api.models import Order
    now = timezone.now()
    expired_qs = Order.objects.filter(
        status="Pending",
        expires_at__isnull=False,
        expires_at__lte=now,
    )
    count = expired_qs.count()
    expired_qs.update(status="Cancelled")
    return f"Expired {count} pending orders"
