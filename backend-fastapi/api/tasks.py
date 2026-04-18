from celery import shared_task
from django.utils import timezone
from datetime import timedelta


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
