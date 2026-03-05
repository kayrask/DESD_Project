from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)
    role = Column(String)  # producer, admin, customer
    full_name = Column(String)
    status = Column(String, default="active")  # active, suspended

    products = relationship("Product", back_populates="producer")
    orders = relationship("Order", back_populates="producer")


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    category = Column(String)
    price = Column(Float)
    stock = Column(Integer)
    status = Column(String)  # Available, Out of Stock
    producer_id = Column(Integer, ForeignKey("users.id"))

    producer = relationship("User", back_populates="products")


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String, unique=True)
    customer_name = Column(String)
    delivery_date = Column(Date)
    status = Column(String)  # Pending, Confirmed
    producer_id = Column(Integer, ForeignKey("users.id"))

    producer = relationship("User", back_populates="orders")