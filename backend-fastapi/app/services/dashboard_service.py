def producer_summary() -> dict:
    return {
        "orders_today": 6,
        "low_stock_products": 2,
        "quick_links": ["products", "orders", "payments"],
    }


def producer_products() -> dict:
    return {
        "items": [
            {"name": "Heirloom Tomatoes", "category": "Vegetable", "price": "$4.50/kg", "stock": 52, "status": "Available"},
            {"name": "Winter Kale", "category": "Leafy Greens", "price": "$3.20/bunch", "stock": 0, "status": "Out of Stock"},
        ]
    }


def producer_orders() -> dict:
    return {
        "items": [
            {"order_id": "D-1023", "customer": "Nazli", "delivery": "2026-03-06", "status": "Pending"},
            {"order_id": "D-1019", "customer": "Ethan", "delivery": "2026-03-05", "status": "Confirmed"},
        ]
    }


def producer_payments() -> dict:
    return {"this_week": 2140.0, "pending": 610.0, "commission": 214.0}


def admin_summary() -> dict:
    return {"commission_today": 482.0, "active_users": 120, "open_flags": 3}


def admin_reports() -> dict:
    return {
        "rows": [
            {"date": "2026-03-01", "orders": 24, "gross": 4820.0, "commission": 482.0},
            {"date": "2026-02-28", "orders": 19, "gross": 3110.0, "commission": 311.0},
        ]
    }


def admin_users() -> dict:
    return {
        "items": [
            {"email": "producer@desd.local", "role": "Producer", "status": "Active"},
            {"email": "customer@desd.local", "role": "Customer", "status": "Active"},
            {"email": "suspended@desd.local", "role": "Customer", "status": "Suspended"},
        ]
    }


def customer_summary() -> dict:
    return {"upcoming_deliveries": 2, "saved_producers": 4}
