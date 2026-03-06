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
        .select("name,category,price,stock,status")
        .eq("producer_id", producer["id"])
        .order("name")
        .execute()
    )
    rows = resp.data or []

    items = [
        {
            "name": row.get("name"),
            "category": row.get("category"),
            "price": f"${float(row.get('price') or 0):.2f}",
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


def producer_payments(user: dict) -> dict:
    # Placeholder shell for Sprint 1.
    return {"this_week": 2140.0, "pending": 610.0, "commission": 214.0}


def admin_summary(user: dict) -> dict:
    client = get_supabase()
    users = client.table("users").select("id").execute().data or []
    return {"commission_today": 482.0, "active_users": len(users), "open_flags": 3}


def admin_reports(user: dict) -> dict:
    # Placeholder shell for Sprint 1.
    return {
        "rows": [
            {"date": "2026-03-01", "orders": 24, "gross": 4820.0, "commission": 482.0},
            {"date": "2026-02-28", "orders": 19, "gross": 3110.0, "commission": 311.0},
        ]
    }


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
