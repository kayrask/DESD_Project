from datetime import date

from app.repositories.auth_repo import find_user_by_email
from app.supabase_client import get_supabase


def producer_summary(user: dict) -> dict:
    producer = find_user_by_email(user["email"])
    if not producer:
        return {"orders_today": 0, "low_stock_products": 0, "quick_links": ["products", "orders", "payments"]}

    client = get_supabase()
    today = date.today().isoformat()

    orders_resp = client.table("orders").select("id").eq("producer_id", producer["id"]).eq("delivery_date", today).execute()
    products_resp = client.table("products").select("id").eq("producer_id", producer["id"]).lt("stock", 10).execute()

    return {
        "orders_today": len(orders_resp.data or []),
        "low_stock_products": len(products_resp.data or []),
        "quick_links": ["products", "orders", "payments"],
    }


def producer_products(user: dict) -> dict:
    producer = find_user_by_email(user["email"])
    if not producer:
        return {"items": []}

    client = get_supabase()
    resp = (
        client.table("products")
        .select("id,name,category,price,stock,status")
        .eq("producer_id", producer["id"])
        .order("name")
        .execute()
    )
    rows = resp.data or []

    items = [
        {
            "id": row.get("id"),
            "name": row.get("name"),
            "category": row.get("category"),
            "price": float(row.get("price") or 0),
            "stock": row.get("stock", 0),
            "status": row.get("status", "Unknown"),
        }
        for row in rows
    ]
    return {"items": items}


def producer_orders(user: dict) -> dict:
    producer = find_user_by_email(user["email"])
    if not producer:
        return {"items": []}

    client = get_supabase()
    resp = (
        client.table("orders")
        .select("order_id,customer_name,delivery_date,status")
        .eq("producer_id", producer["id"])
        .order("delivery_date")
        .execute()
    )
    rows = resp.data or []

    items = [
        {
            "order_id": row.get("order_id"),
            "customer": row.get("customer_name"),
            "delivery": row.get("delivery_date"),
            "status": row.get("status", "Pending"),
        }
        for row in rows
    ]
    return {"items": items}


def create_producer_product(user: dict, payload: dict) -> dict:
    producer = find_user_by_email(user["email"])
    if not producer:
        raise LookupError("Producer account not found")

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

    client = get_supabase()
    response = (
        client.table("products")
        .insert(
            {
                "name": name,
                "category": category,
                "price": round(price, 2),
                "stock": stock,
                "status": status,
                "producer_id": producer["id"],
            }
        )
        .execute()
    )
    rows = response.data or []
    if not rows:
        raise ValueError("Failed to create product")
    return rows[0]


def update_producer_product(user: dict, product_id: int, payload: dict) -> dict:
    producer = find_user_by_email(user["email"])
    if not producer:
        raise LookupError("Producer account not found")

    client = get_supabase()
    existing_resp = (
        client.table("products")
        .select("id,producer_id")
        .eq("id", product_id)
        .limit(1)
        .execute()
    )
    existing_rows = existing_resp.data or []
    if not existing_rows:
        raise LookupError("Product not found")
    if existing_rows[0].get("producer_id") != producer["id"]:
        raise PermissionError("You can only edit your own products")

    updates = {}
    if "name" in payload:
        name = str(payload.get("name", "")).strip()
        if not name:
            raise ValueError("Name cannot be empty")
        updates["name"] = name
    if "category" in payload:
        category = str(payload.get("category", "")).strip()
        if not category:
            raise ValueError("Category cannot be empty")
        updates["category"] = category
    if "price" in payload:
        try:
            price = float(payload.get("price"))
        except (TypeError, ValueError):
            raise ValueError("Price must be numeric")
        if price < 0:
            raise ValueError("Price must be zero or greater")
        updates["price"] = round(price, 2)
    if "stock" in payload:
        try:
            stock = int(payload.get("stock"))
        except (TypeError, ValueError):
            raise ValueError("Stock must be an integer")
        if stock < 0:
            raise ValueError("Stock must be zero or greater")
        updates["stock"] = stock
    if "status" in payload:
        updates["status"] = str(payload.get("status", "")).strip() or "Available"

    if not updates:
        raise ValueError("No valid fields provided for update")

    response = (
        client.table("products")
        .update(updates)
        .eq("id", product_id)
        .eq("producer_id", producer["id"])
        .execute()
    )
    rows = response.data or []
    if not rows:
        raise ValueError("Failed to update product")
    return rows[0]


def producer_order_detail(user: dict, order_id: str) -> dict:
    producer = find_user_by_email(user["email"])
    if not producer:
        raise LookupError("Producer account not found")

    client = get_supabase()
    response = (
        client.table("orders")
        .select("id,order_id,customer_name,delivery_date,status,producer_id")
        .eq("order_id", order_id)
        .eq("producer_id", producer["id"])
        .limit(1)
        .execute()
    )
    rows = response.data or []
    if not rows:
        raise LookupError("Order not found")
    row = rows[0]
    return {
        "id": row.get("id"),
        "order_id": row.get("order_id"),
        "customer": row.get("customer_name"),
        "delivery": row.get("delivery_date"),
        "status": row.get("status", "Pending"),
    }


def update_producer_order_status(user: dict, order_id: str, new_status: str) -> dict:
    producer = find_user_by_email(user["email"])
    if not producer:
        raise LookupError("Producer account not found")

    allowed_transitions = {
        "pending": ["confirmed"],
        "confirmed": ["ready"],
        "ready": ["delivered"],
        "delivered": [],
    }
    normalized_status = (new_status or "").strip().lower()
    if normalized_status not in {"pending", "confirmed", "ready", "delivered"}:
        raise ValueError("Invalid status")

    client = get_supabase()
    current_resp = (
        client.table("orders")
        .select("id,status,producer_id")
        .eq("order_id", order_id)
        .eq("producer_id", producer["id"])
        .limit(1)
        .execute()
    )
    current_rows = current_resp.data or []
    if not current_rows:
        raise LookupError("Order not found")

    current = str(current_rows[0].get("status", "Pending")).strip().lower()
    if normalized_status not in allowed_transitions.get(current, []):
        raise ValueError(f"Invalid status transition from {current} to {normalized_status}")

    response = (
        client.table("orders")
        .update({"status": normalized_status.capitalize()})
        .eq("order_id", order_id)
        .eq("producer_id", producer["id"])
        .execute()
    )
    rows = response.data or []
    if not rows:
        raise ValueError("Failed to update order status")
    row = rows[0]
    return {
        "order_id": row.get("order_id"),
        "status": row.get("status"),
    }


def producer_payments(user: dict) -> dict:
    # Placeholder shell for Sprint 1.
    return {"this_week": 2140.0, "pending": 610.0, "commission": 214.0}


def admin_summary(user: dict) -> dict:
    client = get_supabase()
    users = client.table("users").select("id").execute().data or []
    return {"commission_today": 482.0, "active_users": len(users), "open_flags": 3}


def admin_reports(user: dict, date_from: str | None = None, date_to: str | None = None) -> dict:
    client = get_supabase()
    query = client.table("commission_reports").select("report_date,total_orders,gross_amount,commission_amount").order(
        "report_date", desc=True
    )
    if date_from:
        query = query.gte("report_date", date_from)
    if date_to:
        query = query.lte("report_date", date_to)

    rows = query.execute().data or []
    normalized_rows = [
        {
            "date": row.get("report_date"),
            "orders": int(row.get("total_orders") or 0),
            "gross": float(row.get("gross_amount") or 0),
            "commission": float(row.get("commission_amount") or 0),
        }
        for row in rows
    ]
    return {"rows": normalized_rows}


def admin_users(user: dict) -> dict:
    client = get_supabase()
    resp = client.table("users").select("email,role,status").order("email").execute()
    rows = resp.data or []
    items = [
        {
            "email": row.get("email"),
            "role": str(row.get("role", "")).capitalize(),
            "status": str(row.get("status", "active")).capitalize(),
        }
        for row in rows
    ]
    return {"items": items}


def admin_database(user: dict) -> dict:
    client = get_supabase()
    users = client.table("users").select("id,email,role,full_name,status").order("id").execute().data or []
    products = (
        client.table("products")
        .select("id,name,category,price,stock,status,producer_id")
        .order("id")
        .execute()
        .data
        or []
    )
    orders = (
        client.table("orders")
        .select("id,order_id,customer_name,delivery_date,status,producer_id")
        .order("id")
        .execute()
        .data
        or []
    )
    return {"users": users, "products": products, "orders": orders}


def customer_summary(user: dict) -> dict:
    return {"upcoming_deliveries": 2, "saved_producers": 4}
