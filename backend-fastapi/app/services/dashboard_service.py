from datetime import date

from api.models import CommissionReport, Order, Product, User


def _safe_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _get_producer(email: str) -> User:
    try:
        return User.objects.get(email=email, role="producer")
    except User.DoesNotExist:
        raise LookupError("Producer account not found")


# ── Producer ────────────────────────────────────────────────────────────────

def producer_summary(user: dict) -> dict:
    try:
        producer = _get_producer(user["email"])
    except LookupError:
        return {"orders_today": 0, "low_stock_products": 0, "quick_links": ["products", "orders", "payments"]}

    today = date.today()
    orders_today = Order.objects.filter(producer=producer, delivery_date=today).count()
    low_stock = Product.objects.filter(producer=producer, stock__lt=10).count()

    return {
        "orders_today": orders_today,
        "low_stock_products": low_stock,
        "quick_links": ["products", "orders", "payments"],
    }


def producer_products(user: dict) -> dict:
    try:
        producer = _get_producer(user["email"])
    except LookupError:
        return {"items": []}

    items = [
        {
            "id": p.id,
            "name": p.name,
            "category": p.category,
            "price": _safe_float(p.price),
            "stock": p.stock,
            "status": p.status,
        }
        for p in Product.objects.filter(producer=producer).order_by("name")
    ]
    return {"items": items}


def producer_orders(user: dict) -> dict:
    try:
        producer = _get_producer(user["email"])
    except LookupError:
        return {"items": []}

    items = [
        {
            "order_id": o.order_id,
            "customer": o.customer_name,
            "delivery": o.delivery_date.isoformat() if o.delivery_date else None,
            "status": o.status,
        }
        for o in Order.objects.filter(producer=producer).order_by("delivery_date")
    ]
    return {"items": items}


def create_producer_product(user: dict, payload: dict) -> dict:
    producer = _get_producer(user["email"])

    name = str(payload.get("name", "")).strip()
    category = str(payload.get("category", "")).strip()
    status = str(payload.get("status", "Available")).strip() or "Available"
    try:
        price = float(payload.get("price", 0))
    except (TypeError, ValueError):
        raise ValueError("Price must be numeric")
    try:
        stock = int(payload.get("stock", 0))
    except (TypeError, ValueError):
        raise ValueError("Stock must be an integer")

    if not name or not category:
        raise ValueError("Name and category are required")
    if price < 0:
        raise ValueError("Price must be zero or greater")
    if stock < 0:
        raise ValueError("Stock must be zero or greater")

    if stock == 0:
        status = "Out of Stock"
    elif status.lower() == "out of stock":
        status = "Available"

    product = Product.objects.create(
        name=name,
        category=category,
        price=round(price, 2),
        stock=stock,
        status=status,
        producer=producer,
    )
    return {
        "id": product.id,
        "name": product.name,
        "category": product.category,
        "price": _safe_float(product.price),
        "stock": product.stock,
        "status": product.status,
    }


def update_producer_product(user: dict, product_id: int, payload: dict) -> dict:
    producer = _get_producer(user["email"])

    try:
        product = Product.objects.get(id=product_id)
    except Product.DoesNotExist:
        raise LookupError("Product not found")

    if product.producer_id != producer.id:
        raise PermissionError("You can only edit your own products")

    if "name" in payload:
        name = str(payload.get("name", "")).strip()
        if not name:
            raise ValueError("Name cannot be empty")
        product.name = name
    if "category" in payload:
        category = str(payload.get("category", "")).strip()
        if not category:
            raise ValueError("Category cannot be empty")
        product.category = category
    if "price" in payload:
        try:
            price = float(payload.get("price"))
        except (TypeError, ValueError):
            raise ValueError("Price must be numeric")
        if price < 0:
            raise ValueError("Price must be zero or greater")
        product.price = round(price, 2)
    if "stock" in payload:
        try:
            stock = int(payload.get("stock"))
        except (TypeError, ValueError):
            raise ValueError("Stock must be an integer")
        if stock < 0:
            raise ValueError("Stock must be zero or greater")
        product.stock = stock
    if "status" in payload:
        product.status = str(payload.get("status", "")).strip() or "Available"

    # Keep status in sync with stock.
    if "stock" in payload:
        if product.stock == 0:
            product.status = "Out of Stock"
        elif product.status.lower() == "out of stock":
            product.status = "Available"

    product.save()
    return {
        "id": product.id,
        "name": product.name,
        "category": product.category,
        "price": _safe_float(product.price),
        "stock": product.stock,
        "status": product.status,
    }


def producer_order_detail(user: dict, order_id: str) -> dict:
    producer = _get_producer(user["email"])

    try:
        order = Order.objects.get(order_id=order_id, producer=producer)
    except Order.DoesNotExist:
        raise LookupError("Order not found")

    items = []
    for item in order.items.select_related("product").order_by("id"):
        quantity = item.quantity
        unit_price = _safe_float(item.unit_price)
        items.append({
            "id": item.id,
            "product_id": item.product_id,
            "name": item.product.name,
            "quantity": quantity,
            "unit_price": unit_price,
            "line_total": round(quantity * unit_price, 2),
        })

    return {
        "id": order.id,
        "order_id": order.order_id,
        "customer": order.customer_name,
        "delivery": order.delivery_date.isoformat() if order.delivery_date else None,
        "status": order.status,
        "items_available": len(items) > 0,
        "items": items,
        "order_total": round(sum(i["line_total"] for i in items), 2),
    }


def update_producer_order_status(user: dict, order_id: str, new_status: str) -> dict:
    producer = _get_producer(user["email"])

    allowed_transitions = {
        "pending": ["confirmed"],
        "confirmed": ["ready"],
        "ready": ["delivered"],
        "delivered": [],
    }

    normalized = (new_status or "").strip().lower()
    if normalized not in {"pending", "confirmed", "ready", "delivered"}:
        raise ValueError("Invalid status")

    try:
        order = Order.objects.get(order_id=order_id, producer=producer)
    except Order.DoesNotExist:
        raise LookupError("Order not found")

    current = order.status.strip().lower()
    if normalized not in allowed_transitions.get(current, []):
        raise ValueError(f"Invalid status transition from {current} to {normalized}")

    order.status = normalized.capitalize()
    order.save()
    return {"order_id": order.order_id, "status": order.status}


def producer_payments(user: dict) -> dict:
    return {"this_week": 2140.0, "pending": 610.0, "commission": 214.0}


# ── Admin ────────────────────────────────────────────────────────────────────

def admin_summary(user: dict) -> dict:
    active_users = User.objects.filter(status="active").count()
    return {"commission_today": 482.0, "active_users": active_users, "open_flags": 3}


def admin_reports(user: dict, date_from: str | None = None, date_to: str | None = None) -> dict:
    qs = CommissionReport.objects.all()
    if date_from:
        qs = qs.filter(report_date__gte=date_from)
    if date_to:
        qs = qs.filter(report_date__lte=date_to)

    rows = [
        {
            "date": str(r.report_date),
            "orders": r.total_orders,
            "gross": float(r.gross_amount),
            "commission": float(r.commission_amount),
        }
        for r in qs
    ]
    return {"rows": rows}


def admin_users(user: dict) -> dict:
    items = [
        {
            "email": u.email,
            "role": u.role.capitalize(),
            "status": u.status.capitalize(),
        }
        for u in User.objects.all().order_by("email")
    ]
    return {"items": items}


def admin_database(user: dict) -> dict:
    users = list(User.objects.values("id", "email", "role", "full_name", "status").order_by("id"))
    products = list(
        Product.objects.values("id", "name", "category", "price", "stock", "status", "producer_id").order_by("id")
    )
    orders = list(
        Order.objects.values("id", "order_id", "customer_name", "delivery_date", "status", "producer_id").order_by("id")
    )
    # Convert Decimal/date to JSON-serialisable types
    for p in products:
        p["price"] = float(p["price"])
    for o in orders:
        if o["delivery_date"]:
            o["delivery_date"] = str(o["delivery_date"])
    return {"users": users, "products": products, "orders": orders}


# ── Customer ─────────────────────────────────────────────────────────────────

def customer_summary(user: dict) -> dict:
    return {"upcoming_deliveries": 2, "saved_producers": 4}


# ── Marketplace ───────────────────────────────────────────────────────────────

def marketplace_producers() -> dict:
    items = [
        {
            "id": u.id,
            "name": u.full_name or u.email.split("@")[0],
            "status": u.status,
        }
        for u in User.objects.filter(role="producer").order_by("full_name")
    ]
    return {"items": items}
