#!/usr/bin/env python3

from app.database import engine, Base, SessionLocal
from app.models.models import User, Product, Order
from app.repositories.auth_repo import create_user
from datetime import date

def populate_db():
    # Create tables
    Base.metadata.create_all(bind=engine)

    # Clear existing data
    db = SessionLocal()
    try:
        db.query(Order).delete()
        db.query(Product).delete()
        db.query(User).delete()
        db.commit()
    except:
        db.rollback()
    finally:
        db.close()

    # Create users
    producer = create_user("producer@desd.local", "password123", "producer", "Producer User")
    admin = create_user("admin@desd.local", "password123", "admin", "Admin User")
    customer = create_user("customer@desd.local", "password123", "customer", "Customer User")
    suspended = create_user("suspended@desd.local", "password123", "customer", "Suspended User")
    suspended.status = "suspended"

    db = SessionLocal()
    try:
        # Add suspended user
        db.add(suspended)
        db.commit()

        # Create products for producer
        product1 = Product(name="Heirloom Tomatoes", category="Vegetable", price=4.50, stock=52, status="Available", producer_id=producer.id)
        product2 = Product(name="Winter Kale", category="Leafy Greens", price=3.20, stock=0, status="Out of Stock", producer_id=producer.id)
        db.add(product1)
        db.add(product2)

        # Create orders for producer
        order1 = Order(order_id="D-1023", customer_name="John Smith", delivery_date=date(2026, 3, 6), status="Pending", producer_id=producer.id)
        order2 = Order(order_id="D-1019", customer_name="Jane Doe", delivery_date=date(2026, 3, 5), status="Confirmed", producer_id=producer.id)
        db.add(order1)
        db.add(order2)

        db.commit()
        print("Database populated successfully!")
    finally:
        db.close()

if __name__ == "__main__":
    populate_db()