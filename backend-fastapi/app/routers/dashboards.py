from fastapi import APIRouter, Header

from app.core.security import require_role, user_from_token
from app.services.dashboard_service import (
    admin_reports,
    admin_summary,
    admin_users,
    customer_summary,
    producer_orders,
    producer_payments,
    producer_products,
    producer_summary,
)

router = APIRouter(prefix="/dashboards", tags=["dashboards"])


@router.get("/me")
def whoami(authorization: str | None = Header(default=None)) -> dict:
    return user_from_token(authorization)


@router.get("/producer")
def producer_dashboard(authorization: str | None = Header(default=None)) -> dict:
    user = user_from_token(authorization)
    require_role(user, ["producer"])
    return producer_summary()


@router.get("/producer/products")
def producer_products_data(authorization: str | None = Header(default=None)) -> dict:
    user = user_from_token(authorization)
    require_role(user, ["producer"])
    return producer_products()


@router.get("/producer/orders")
def producer_orders_data(authorization: str | None = Header(default=None)) -> dict:
    user = user_from_token(authorization)
    require_role(user, ["producer"])
    return producer_orders()


@router.get("/producer/payments")
def producer_payments_data(authorization: str | None = Header(default=None)) -> dict:
    user = user_from_token(authorization)
    require_role(user, ["producer"])
    return producer_payments()


@router.get("/admin")
def admin_dashboard(authorization: str | None = Header(default=None)) -> dict:
    user = user_from_token(authorization)
    require_role(user, ["admin"])
    return admin_summary()


@router.get("/admin/reports")
def admin_reports_data(authorization: str | None = Header(default=None)) -> dict:
    user = user_from_token(authorization)
    require_role(user, ["admin"])
    return admin_reports()


@router.get("/admin/users")
def admin_users_data(authorization: str | None = Header(default=None)) -> dict:
    user = user_from_token(authorization)
    require_role(user, ["admin"])
    return admin_users()


@router.get("/customer")
def customer_dashboard(authorization: str | None = Header(default=None)) -> dict:
    user = user_from_token(authorization)
    require_role(user, ["customer"])
    return customer_summary()
