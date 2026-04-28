from django.conf import settings
from django.utils import timezone
from django.db.models import Q


def cart_context(request):
    """Inject cart_count into every template so the navbar badge stays current."""
    cart = request.session.get("cart", [])
    cart_count = sum(int(i.get("quantity", 0)) for i in cart)
    return {"cart_count": cart_count}


def session_context(request):
    """
    Inject session expiry information so the base template can warn the user
    when their session is about to expire.

    Provides:
      session_expires_in_seconds  — seconds remaining (int), or None if not logged in
      session_warn                — True when < 5 minutes remain
    """
    if not request.user.is_authenticated:
        return {"session_expires_in_seconds": None, "session_warn": False}

    session_age = getattr(settings, "SESSION_COOKIE_AGE", 3600)
    last_activity = request.session.get("_session_last_activity")

    if last_activity:
        elapsed = int(timezone.now().timestamp()) - last_activity
        remaining = max(0, session_age - elapsed)
    else:
        remaining = session_age

    # Stamp last-activity every request so the timer resets on activity.
    request.session["_session_last_activity"] = int(timezone.now().timestamp())

    warn = remaining < 300  # warn when fewer than 5 minutes remain
    return {"session_expires_in_seconds": remaining, "session_warn": warn}


def recurring_order_notifications_context(request):
    """Inject pending recurring order notification count for the navbar badge."""
    if not request.user.is_authenticated or getattr(request.user, "role", None) != "customer":
        return {"recurring_notification_count": 0}
    try:
        from api.models import RecurringOrderNotification
        count = RecurringOrderNotification.objects.filter(
            recurring_order__customer=request.user,
            requires_action=True,
            is_read=False,
        ).count()
    except Exception:
        count = 0
    return {"recurring_notification_count": count}
