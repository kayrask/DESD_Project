from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.models import User, Product, Order
from app.repositories.auth_repo import find_user_by_email


def producer_summary(user: dict) -> dict:
    db: Session = SessionLocal()
    try:
        producer = db.query(User).filter(User.email == user["email"]).first()
        if not producer:
            return {"orders_today": 0, "low_stock_products": 0, "quick_links": ["products", "orders", "payments"]}

        # Count orders today (simplified, assuming today is 2026-03-05 or something)
        orders_today = db.query(Order).filter(Order.producer_id == producer.id, Order.delivery_date == "2026-03-05").count()

        # Low stock: stock < 10
        low_stock = db.query(Product).filter(Product.producer_id == producer.id, Product.stock < 10).count()

        return {
            "orders_today": orders_today,
            "low_stock_products": low_stock,
            "quick_links": ["products", "orders", "payments"],
        }
    finally:
        db.close()


def producer_products(user: dict) -> dict:
    db: Session = SessionLocal()
    try:
        producer = db.query(User).filter(User.email == user["email"]).first()
        if not producer:
            return {"items": []}

        products = db.query(Product).filter(Product.producer_id == producer.id).all()
        items = [
            {
                "name": p.name,
                "category": p.category,
                "price": f"${p.price:.2f}/kg" if "kg" in p.name.lower() else f"${p.price:.2f}/bunch",
                "stock": p.stock,
                "status": p.status
            }
            for p in products
        ]
        return {"items": items}
    finally:
        db.close()


def producer_orders(user: dict) -> dict:
    db: Session = SessionLocal()
    try:
        producer = db.query(User).filter(User.email == user["email"]).first()
        if not producer:
            return {"items": []}

        orders = db.query(Order).filter(Order.producer_id == producer.id).all()
        items = [
            {
                "order_id": o.order_id,
                "customer": o.customer_name,
                "delivery": str(o.delivery_date),
                "status": o.status
            }
            for o in orders
        ]
        return {"items": items}
    finally:
        db.close()


def producer_payments(user: dict) -> dict:
    # Simplified, hardcoded for now
    return {"this_week": 2140.0, "pending": 610.0, "commission": 214.0}


def admin_summary(user: dict) -> dict:
    # Simplified
    return {"commission_today": 482.0, "active_users": 120, "open_flags": 3}


def admin_reports(user: dict) -> dict:
    # Simplified
    return {
        "rows": [
            {"date": "2026-03-01", "orders": 24, "gross": 4820.0, "commission": 482.0},
            {"date": "2026-02-28", "orders": 19, "gross": 3110.0, "commission": 311.0},
        ]
    }


def admin_users(user: dict) -> dict:
    db: Session = SessionLocal()
    try:
        users = db.query(User).all()
        items = [
            {"email": u.email, "role": u.role.capitalize(), "status": u.status.capitalize()}
            for u in users
        ]
        return {"items": items}
    finally:
        db.close()


def admin_database(user: dict) -> dict:
    db: Session = SessionLocal()
    try:
        users = db.query(User).all()
        products = db.query(Product).all()
        orders = db.query(Order).all()
        return {
            "users": [{"id": u.id, "email": u.email, "role": u.role, "full_name": u.full_name, "status": u.status} for u in users],
            "products": [{"id": p.id, "name": p.name, "category": p.category, "price": p.price, "stock": p.stock, "status": p.status, "producer_id": p.producer_id} for p in products],
            "orders": [{"id": o.id, "order_id": o.order_id, "customer_name": o.customer_name, "delivery_date": str(o.delivery_date), "status": o.status, "producer_id": o.producer_id} for o in orders]
        }
    finally:
        db.close()


def customer_summary(user: dict) -> dict:
    return {"upcoming_deliveries": 2, "saved_producers": 4}
