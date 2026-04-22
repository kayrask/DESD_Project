import pathlib

from celery import shared_task
from django.utils import timezone
from datetime import timedelta

_DATASET_PATH = pathlib.Path(__file__).resolve().parent.parent / "ml" / "Fruit And Vegetable Diseases Dataset"
_METRICS_PATH = pathlib.Path(__file__).resolve().parent.parent / "ml" / "saved_models" / "model_metrics.json"


@shared_task(max_retries=0)
def evaluate_model_after_upload(model_version: str):
    """Run ml.evaluate in a subprocess after a new model is uploaded.

    Running as a subprocess keeps PyTorch memory isolated from the Celery
    worker process — avoids OOM when multiple uploads happen concurrently.
    """
    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable, "-m", "ml.evaluate",
            "--data_dir", str(_DATASET_PATH),
            "--model_version", model_version,
        ],
        capture_output=True,
        text=True,
        cwd=str(pathlib.Path(__file__).resolve().parent.parent),
    )
    if result.returncode != 0:
        raise RuntimeError(f"ml.evaluate failed:\n{result.stderr}")
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
