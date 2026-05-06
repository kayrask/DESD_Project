import pathlib

from celery import shared_task
from django.db import models
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


@shared_task
def send_high_demand_alerts():
    """
    Check SARIMA demand forecasts for all producers' products.
    Send an email to each producer whose products have high demand expected
    in the next week. Runs daily (registered in setup_periodic_tasks).
    """
    from django.core.mail import send_mail
    from api.models import Product, User
    from app.services.forecast_service import get_demand_forecast

    producers = User.objects.filter(role="producer", is_active=True)
    emails_sent = 0

    for producer in producers:
        products = Product.objects.filter(
            producer=producer,
            status__in=["Available", "In Season"],
            stock__gt=0,
        )
        high_demand_products = []
        for product in products:
            try:
                fc = get_demand_forecast(product.id, weeks=1)
                if fc.get("high_demand"):
                    high_demand_products.append(
                        f"  • {product.name} — forecast {sum(fc['predicted_units']):.0f} units next week"
                    )
            except Exception:
                continue

        if not high_demand_products:
            continue

        product_list = "\n".join(high_demand_products)
        send_mail(
            subject="[DESD] High demand forecast for your products",
            message=(
                f"Hello {producer.full_name},\n\n"
                f"Our AI demand model predicts high demand for the following products next week:\n\n"
                f"{product_list}\n\n"
                f"Consider restocking soon to avoid running out of stock.\n\n"
                f"— DESD AI Team"
            ),
            from_email="noreply@desd.local",
            recipient_list=[producer.email],
            fail_silently=True,
        )
        emails_sent += 1

    return f"High demand alerts sent to {emails_sent} producer(s)"


@shared_task
def send_reorder_reminders():
    """
    Run the reorder prediction model for all customers.
    Send a personalised reorder reminder email to customers who have
    at least one product with predicted reorder probability > 0.7.
    Runs weekly (registered in setup_periodic_tasks).
    """
    from django.core.mail import send_mail
    from api.models import User
    from app.services.reorder_service import predict_reorder_items

    customers = User.objects.filter(role="customer", is_active=True)
    emails_sent = 0

    for customer in customers:
        try:
            suggestions = [
                s for s in predict_reorder_items(customer.full_name)
                if s.get("source") == "model" and s.get("probability", 0) >= 0.7
            ]
        except Exception:
            continue

        if not suggestions:
            continue

        item_lines = "\n".join(
            f"  • {s['name']} — £{s['price']} ({s['reason']})"
            for s in suggestions[:3]
        )
        send_mail(
            subject="[DESD] Time to restock? Your weekly reorder suggestions",
            message=(
                f"Hello {customer.full_name},\n\n"
                f"Based on your ordering history, our AI thinks you might need:\n\n"
                f"{item_lines}\n\n"
                f"Log in to add them to your cart: http://localhost/customer/dashboard/\n\n"
                f"— DESD AI Team"
            ),
            from_email="noreply@desd.local",
            recipient_list=[customer.email],
            fail_silently=True,
        )
        emails_sent += 1

    return f"Reorder reminders sent to {emails_sent} customer(s)"


@shared_task
def fire_recurring_orders():
    """
    Process all active recurring orders whose next_order_date is today or overdue.

    For each due order:
    - If past end_date: mark completed.
    - If price changed, out of stock, or quantity unavailable: pause the order,
      create a RecurringOrderNotification, and email the customer.
    - If all checks pass: place the order (CheckoutOrder + vendor Orders + OrderItems),
      decrement stock, and advance next_order_date.

    Runs daily via Celery Beat.
    """
    from datetime import date, timedelta
    from decimal import Decimal
    from collections import defaultdict

    from django.core.mail import send_mail
    from django.utils import timezone

    from api.models import (
        RecurringOrder, RecurringOrderNotification,
        Product, CheckoutOrder, Order, OrderItem, CommissionReport,
    )

    _COMMISSION_RATE = Decimal("0.05")
    today = date.today()

    due = RecurringOrder.objects.filter(
        status=RecurringOrder.STATUS_ACTIVE,
        next_order_date__lte=today,
    ).select_related("customer")

    placed = 0
    paused = 0
    completed = 0

    for ro in due:
        # ── Past end date → mark completed ───────────────────────────────────
        if ro.end_date and today > ro.end_date:
            ro.status = RecurringOrder.STATUS_COMPLETED
            ro.is_active = False
            ro.save(update_fields=["status", "is_active"])
            completed += 1
            continue

        # ── Check each item for issues ────────────────────────────────────────
        issue_type = None
        issue_item_name = ""
        issue_product = None

        for item in ro.items:
            try:
                product = Product.objects.get(pk=item["product_id"])
            except Product.DoesNotExist:
                issue_type = RecurringOrder.PAUSE_STOCK
                issue_item_name = item.get("name", "item")
                break

            # Price change check
            stored_price = float(item.get("price", 0))
            current_price = float(product.price)
            if abs(current_price - stored_price) > 0.001:
                if ro.on_price_change == RecurringOrder.PREF_NOTIFY:
                    issue_type = RecurringOrder.PAUSE_PRICE
                    issue_item_name = item.get("name", product.name)
                    issue_product = product
                    break
                else:
                    # Auto-continue — update stored price in-place
                    item["price"] = current_price

            # Out of stock check — always pause, can't auto-continue
            if product.status == "Out of Stock" or product.stock < 1:
                issue_type = RecurringOrder.PAUSE_STOCK
                issue_item_name = item.get("name", product.name)
                break

            # Quantity check
            if product.stock < int(item.get("quantity", 1)):
                if ro.on_quantity_change == RecurringOrder.PREF_NOTIFY:
                    issue_type = RecurringOrder.PAUSE_QTY
                    issue_item_name = item.get("name", product.name)
                    issue_product = product
                    break
                # else auto-continue with whatever stock is available

        # ── Issue found → pause and notify ───────────────────────────────────
        if issue_type:
            ro.status = RecurringOrder.STATUS_PAUSED
            ro.pause_reason = issue_type
            ro.save(update_fields=["status", "pause_reason"])

            if issue_type == RecurringOrder.PAUSE_PRICE:
                old = item.get("price", 0)
                new = float(issue_product.price)
                msg = (
                    f"The price of {issue_item_name} has changed from "
                    f"£{old:.2f} to £{new:.2f}. "
                    f"Please confirm whether you'd like to continue at the new price."
                )
            elif issue_type == RecurringOrder.PAUSE_STOCK:
                msg = (
                    f"{issue_item_name} is currently out of stock. "
                    f"Your recurring order has been paused until you approve it."
                )
            else:
                avail = issue_product.stock if issue_product else 0
                msg = (
                    f"The requested quantity of {issue_item_name} is not fully available "
                    f"(only {avail} in stock). "
                    f"Please approve or cancel your recurring order."
                )

            RecurringOrderNotification.objects.create(
                recurring_order=ro,
                notification_type=issue_type,
                message=msg,
                requires_action=True,
            )
            send_mail(
                subject="Your recurring order needs attention — DESD",
                message=(
                    f"Hi {ro.customer.full_name},\n\n{msg}\n\n"
                    f"Log in to review: http://localhost/customer/recurring-orders/\n\n"
                    f"— DESD Marketplace"
                ),
                from_email="noreply@desd.local",
                recipient_list=[ro.customer.email],
                fail_silently=True,
            )
            paused += 1
            continue

        # ── All checks pass → place the order ────────────────────────────────
        try:
            checkout_order = CheckoutOrder.objects.create(
                full_name=ro.customer.full_name,
                email=ro.customer.email,
                address="Recurring order — address on file",
                city="",
                postal_code="",
                payment_method="recurring",
                delivery_date=ro.next_order_date,
                special_instructions=ro.notes or "",
                customer=ro.customer,
                status="pending",
            )

            # Group items by producer
            product_ids = [int(i["product_id"]) for i in ro.items]
            products_map = {p.id: p for p in Product.objects.filter(pk__in=product_ids)}

            grouped = defaultdict(list)
            gross_total = Decimal("0.00")
            for item in ro.items:
                product = products_map.get(int(item["product_id"]))
                if not product:
                    continue
                qty = int(item["quantity"])
                grouped[product.producer_id].append((product, qty))
                gross_total += Decimal(str(product.price)) * qty

            base_order_id = f"RO-{ro.id}-{checkout_order.id}"
            is_multi = len(grouped) > 1

            for producer_id, lines in grouped.items():
                producer = lines[0][0].producer
                vendor_id = base_order_id if not is_multi else f"{base_order_id}-{producer_id}"
                subtotal = sum(Decimal(str(p.price)) * qty for p, qty in lines)
                commission = (subtotal * _COMMISSION_RATE).quantize(Decimal("0.01"))

                vendor_order = Order.objects.create(
                    order_id=vendor_id,
                    customer_name=ro.customer.full_name,
                    delivery_date=ro.next_order_date,
                    status="Pending",
                    producer=producer,
                    expires_at=timezone.now() + timedelta(hours=48),
                    commission=commission,
                )
                for product, qty in lines:
                    OrderItem.objects.create(
                        order=vendor_order,
                        product=product,
                        quantity=qty,
                        unit_price=product.price,
                    )

            # Decrement stock
            for item in ro.items:
                product = products_map.get(int(item["product_id"]))
                if not product:
                    continue
                product.stock = max(0, product.stock - int(item["quantity"]))
                if product.stock == 0:
                    product.status = "Out of Stock"
                product.save(update_fields=["stock", "status"])

            # Update commission report
            report_date = today
            commission_total = (gross_total * _COMMISSION_RATE).quantize(Decimal("0.01"))
            report, _ = CommissionReport.objects.get_or_create(
                report_date=report_date,
                defaults={"total_orders": 0, "gross_amount": Decimal("0.00"), "commission_amount": Decimal("0.00")},
            )
            report.total_orders += 1
            report.gross_amount = (Decimal(str(report.gross_amount)) + gross_total).quantize(Decimal("0.01"))
            report.commission_amount = (Decimal(str(report.commission_amount)) + commission_total).quantize(Decimal("0.01"))
            report.save()

            # Notify customer — order placed successfully
            RecurringOrderNotification.objects.create(
                recurring_order=ro,
                notification_type=RecurringOrderNotification.TYPE_PLACED,
                message=f"Your recurring order was automatically placed (ref: {base_order_id}).",
                requires_action=False,
            )
            send_mail(
                subject="Recurring order placed — DESD",
                message=(
                    f"Hi {ro.customer.full_name},\n\n"
                    f"Your recurring order has been automatically placed (ref: {base_order_id}).\n\n"
                    f"— DESD Marketplace"
                ),
                from_email="noreply@desd.local",
                recipient_list=[ro.customer.email],
                fail_silently=True,
            )

            # Advance next_order_date
            delta = timedelta(weeks=1) if ro.recurrence == "weekly" else timedelta(weeks=2)
            next_date = ro.next_order_date + delta
            if ro.end_date and next_date > ro.end_date:
                ro.status = RecurringOrder.STATUS_COMPLETED
                ro.is_active = False
            ro.next_order_date = next_date
            ro.save(update_fields=["next_order_date", "status", "is_active"])
            placed += 1

        except Exception as exc:
            # Don't let one bad order stop the rest
            import logging
            logging.getLogger(__name__).exception("Failed to place recurring order #%s: %s", ro.id, exc)

    return f"Recurring orders: {placed} placed, {paused} paused, {completed} completed"


@shared_task
def process_weekly_settlements():
    """
    Create weekly PaymentSettlement records for all producers.

    Runs every Monday morning. Covers delivered orders whose delivery_date
    falls within the previous Mon–Sun week. Each settlement records the gross
    sales, 5% platform commission, and 95% net payout. Idempotent — uses
    get_or_create so re-running on the same day is safe.
    """
    from datetime import date, timedelta
    from decimal import Decimal
    from api.models import Order, User, PaymentSettlement

    _COMMISSION_RATE = Decimal("0.05")
    today = date.today()

    # Determine the previous Mon–Sun week
    days_since_monday = today.weekday()          # 0=Mon … 6=Sun
    this_monday = today - timedelta(days=days_since_monday)
    week_end = this_monday - timedelta(days=1)   # Previous Sunday
    week_start = week_end - timedelta(days=6)    # Previous Monday

    producers = User.objects.filter(role="producer", is_active=True)
    created_count = 0

    for producer in producers:
        delivered_orders = Order.objects.filter(
            producer=producer,
            status="Delivered",
            delivery_date__gte=week_start,
            delivery_date__lte=week_end,
        ).prefetch_related("items")

        if not delivered_orders.exists():
            continue

        gross = Decimal("0.00")
        for order in delivered_orders:
            for item in order.items.all():
                gross += Decimal(str(item.unit_price)) * item.quantity
        gross = gross.quantize(Decimal("0.01"))
        commission = (gross * _COMMISSION_RATE).quantize(Decimal("0.01"))
        net = (gross - commission).quantize(Decimal("0.01"))
        order_count = delivered_orders.count()

        week_num = week_start.isocalendar()[1]
        reference = f"SETTLE-{week_start.year}-W{week_num:02d}-{producer.id}"

        _, created = PaymentSettlement.objects.get_or_create(
            producer=producer,
            week_start=week_start,
            defaults={
                "reference": reference,
                "week_end": week_end,
                "gross_amount": gross,
                "commission_amount": commission,
                "net_amount": net,
                "order_count": order_count,
                "status": PaymentSettlement.STATUS_PENDING,
            },
        )
        if created:
            created_count += 1

    return f"Weekly settlements processed: {created_count} new records"


@shared_task
def send_low_stock_alerts():
    """
    Notify each producer by email for any product whose stock has dropped
    at or below its low_stock_threshold. Runs daily.
    """
    from django.core.mail import send_mail
    from api.models import Product

    low_stock_products = (
        Product.objects.filter(
            stock__lte=models.F("low_stock_threshold"),
            low_stock_threshold__gt=0,
            status__in=["Available", "In Season"],
        )
        .select_related("producer")
    )

    producer_map: dict = {}
    for product in low_stock_products:
        producer_map.setdefault(product.producer, []).append(product)

    emails_sent = 0
    for producer, products in producer_map.items():
        lines = "\n".join(
            f"  • {p.name} — {p.stock} unit(s) remaining (threshold: {p.low_stock_threshold})"
            for p in products
        )
        send_mail(
            subject="[DESD] Low stock alert for your products",
            message=(
                f"Hello {producer.full_name},\n\n"
                f"The following product(s) are running low on stock:\n\n"
                f"{lines}\n\n"
                f"Please restock soon to avoid order failures.\n\n"
                f"— DESD Marketplace"
            ),
            from_email="noreply@desd.local",
            recipient_list=[producer.email],
            fail_silently=True,
        )
        emails_sent += 1

    return f"Low stock alerts sent to {emails_sent} producer(s)"
