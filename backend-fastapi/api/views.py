from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from app.core.security import ApiAuthError, issue_token, require_role, revoke_token, user_from_token
from app.repositories.auth_repo import find_user_by_email, register_user, verify_password
from app.services.dashboard_service import (
    admin_database,
    admin_reports,
    admin_summary,
    admin_users,
    create_producer_product,
    customer_summary,
    producer_order_detail,
    producer_orders,
    producer_payments,
    producer_products,
    producer_summary,
    update_producer_order_status,
    update_producer_product,
)
from app.services.ai_service import recommend_products
from app.supabase_client import get_supabase


def _error_response(error: str, message: str, code: int) -> Response:
    return Response({"error": error, "message": message}, status=code)


def _auth_header(request) -> str | None:
    return request.META.get("HTTP_AUTHORIZATION")


def _require_user(request) -> dict | Response:
    try:
        return user_from_token(_auth_header(request))
    except ApiAuthError as exc:
        return _error_response(exc.error, exc.message, exc.status_code)


def _validate_password(password: str) -> bool:
    has_min_length = len(password) >= 8
    has_upper = any(char.isupper() for char in password)
    has_lower = any(char.islower() for char in password)
    has_digit = any(char.isdigit() for char in password)
    return has_min_length and has_upper and has_lower and has_digit


@api_view(["GET"])
def health(_request):
    return Response({"status": "ok"})


@csrf_exempt
@api_view(["POST"])
def auth_login(request):
    email = str(request.data.get("email", "")).strip()
    password = str(request.data.get("password", ""))

    if not email or not password:
        return _error_response("validation_error", "Invalid request data", status.HTTP_400_BAD_REQUEST)

    user = find_user_by_email(email)
    if not user or not verify_password(password, user.get("password_hash", "")):
        return _error_response("unauthenticated", "Invalid email or password", status.HTTP_401_UNAUTHORIZED)

    payload = {
        "email": user.get("email"),
        "role": user.get("role"),
        "full_name": user.get("full_name"),
    }
    token = issue_token(payload)
    return Response({"access_token": token, "token_type": "bearer", "user": payload})


@csrf_exempt
@api_view(["POST"])
def auth_register(request):
    email = str(request.data.get("email", "")).strip()
    password = str(request.data.get("password", ""))
    role = str(request.data.get("role", "")).strip().lower()
    full_name = str(request.data.get("full_name", "")).strip()

    if not email or not password or not role or not full_name:
        return _error_response("validation_error", "Invalid request data", status.HTTP_400_BAD_REQUEST)

    if role not in {"customer", "producer", "admin"}:
        return _error_response("validation_error", "Invalid role", status.HTTP_400_BAD_REQUEST)

    if not _validate_password(password):
        return _error_response(
            "validation_error",
            "Password must contain at least 8 characters, including upper, lower, and number.",
            status.HTTP_400_BAD_REQUEST,
        )

    try:
        user = register_user(email, password, role, full_name)
        return Response(
            {
                "message": "User registered successfully",
                "user": {
                    "email": user.get("email"),
                    "role": user.get("role"),
                    "full_name": user.get("full_name"),
                },
            }
        )
    except ValueError as exc:
        return _error_response("validation_error", str(exc), status.HTTP_400_BAD_REQUEST)


@csrf_exempt
@api_view(["POST"])
def auth_logout(request):
    try:
        revoke_token(_auth_header(request))
        return Response({"message": "Logged out successfully"})
    except ApiAuthError as exc:
        return _error_response(exc.error, exc.message, exc.status_code)


@api_view(["GET"])
def dashboards_me(request):
    user = _require_user(request)
    if isinstance(user, Response):
        return user
    return Response(user)


@api_view(["GET"])
def dashboards_producer(request):
    user = _require_user(request)
    if isinstance(user, Response):
        return user
    try:
        require_role(user, ["producer"])
        return Response(producer_summary(user))
    except ApiAuthError as exc:
        return _error_response(exc.error, exc.message, exc.status_code)


@api_view(["GET"])
def dashboards_producer_products(request):
    user = _require_user(request)
    if isinstance(user, Response):
        return user
    try:
        require_role(user, ["producer"])
        return Response(producer_products(user))
    except ApiAuthError as exc:
        return _error_response(exc.error, exc.message, exc.status_code)


@api_view(["GET"])
def dashboards_producer_orders(request):
    user = _require_user(request)
    if isinstance(user, Response):
        return user
    try:
        require_role(user, ["producer"])
        return Response(producer_orders(user))
    except ApiAuthError as exc:
        return _error_response(exc.error, exc.message, exc.status_code)


@csrf_exempt
@api_view(["POST"])
def producer_products_create(request):
    user = _require_user(request)
    if isinstance(user, Response):
        return user
    try:
        require_role(user, ["producer"])
        product = create_producer_product(user, request.data)
        return Response({"message": "Product created", "data": product}, status=status.HTTP_201_CREATED)
    except ApiAuthError as exc:
        return _error_response(exc.error, exc.message, exc.status_code)
    except (ValueError, LookupError, PermissionError) as exc:
        return _error_response("validation_error", str(exc), status.HTTP_400_BAD_REQUEST)


@csrf_exempt
@api_view(["PATCH"])
def producer_products_update(request, product_id: int):
    user = _require_user(request)
    if isinstance(user, Response):
        return user
    try:
        require_role(user, ["producer"])
        product = update_producer_product(user, product_id, request.data)
        return Response({"message": "Product updated", "data": product})
    except ApiAuthError as exc:
        return _error_response(exc.error, exc.message, exc.status_code)
    except LookupError as exc:
        return _error_response("not_found", str(exc), status.HTTP_404_NOT_FOUND)
    except PermissionError as exc:
        return _error_response("forbidden", str(exc), status.HTTP_403_FORBIDDEN)
    except ValueError as exc:
        return _error_response("validation_error", str(exc), status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
def dashboards_producer_payments(request):
    user = _require_user(request)
    if isinstance(user, Response):
        return user
    try:
        require_role(user, ["producer"])
        return Response(producer_payments(user))
    except ApiAuthError as exc:
        return _error_response(exc.error, exc.message, exc.status_code)


@api_view(["GET"])
def producer_order_get(request, order_id: str):
    user = _require_user(request)
    if isinstance(user, Response):
        return user
    try:
        require_role(user, ["producer"])
        return Response(producer_order_detail(user, order_id))
    except ApiAuthError as exc:
        return _error_response(exc.error, exc.message, exc.status_code)
    except LookupError as exc:
        return _error_response("not_found", str(exc), status.HTTP_404_NOT_FOUND)


@csrf_exempt
@api_view(["PATCH"])
def producer_order_status_update(request, order_id: str):
    user = _require_user(request)
    if isinstance(user, Response):
        return user
    next_status = str(request.data.get("status", ""))
    try:
        require_role(user, ["producer"])
        result = update_producer_order_status(user, order_id, next_status)
        return Response({"message": "Order status updated", "data": result})
    except ApiAuthError as exc:
        return _error_response(exc.error, exc.message, exc.status_code)
    except LookupError as exc:
        return _error_response("not_found", str(exc), status.HTTP_404_NOT_FOUND)
    except ValueError as exc:
        return _error_response("validation_error", str(exc), status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
def dashboards_admin(request):
    user = _require_user(request)
    if isinstance(user, Response):
        return user
    try:
        require_role(user, ["admin"])
        return Response(admin_summary(user))
    except ApiAuthError as exc:
        return _error_response(exc.error, exc.message, exc.status_code)


@api_view(["GET"])
def dashboards_admin_reports(request):
    user = _require_user(request)
    if isinstance(user, Response):
        return user
    try:
        require_role(user, ["admin"])
        date_from = request.GET.get("from")
        date_to = request.GET.get("to")
        return Response(admin_reports(user, date_from=date_from, date_to=date_to))
    except ApiAuthError as exc:
        return _error_response(exc.error, exc.message, exc.status_code)


@api_view(["GET"])
def dashboards_admin_users(request):
    user = _require_user(request)
    if isinstance(user, Response):
        return user
    try:
        require_role(user, ["admin"])
        return Response(admin_users(user))
    except ApiAuthError as exc:
        return _error_response(exc.error, exc.message, exc.status_code)


@api_view(["GET"])
def dashboards_admin_database(request):
    user = _require_user(request)
    if isinstance(user, Response):
        return user
    try:
        require_role(user, ["admin"])
        return Response(admin_database(user))
    except ApiAuthError as exc:
        return _error_response(exc.error, exc.message, exc.status_code)


@api_view(["GET"])
def dashboards_customer(request):
    user = _require_user(request)
    if isinstance(user, Response):
        return user
    try:
        require_role(user, ["customer"])
        return Response(customer_summary(user))
    except ApiAuthError as exc:
        return _error_response(exc.error, exc.message, exc.status_code)


@csrf_exempt
@api_view(["POST"])
def orders_create(request):
    required = ["fullName", "email", "address", "city", "postalCode", "paymentMethod"]
    missing = [field for field in required if not request.data.get(field)]
    if missing:
        return _error_response("validation_error", "Invalid request data", status.HTTP_400_BAD_REQUEST)

    try:
        supabase = get_supabase()
        response = (
            supabase.table("checkout_orders")
            .insert(
                {
                    "full_name": request.data.get("fullName"),
                    "email": request.data.get("email"),
                    "address": request.data.get("address"),
                    "city": request.data.get("city"),
                    "postal_code": request.data.get("postalCode"),
                    "payment_method": request.data.get("paymentMethod"),
                    "status": "pending",
                }
            )
            .execute()
        )

        if response.data:
            return Response(
                {
                    "id": response.data[0].get("id"),
                    "message": "Order created successfully",
                    "data": response.data[0],
                },
                status=status.HTTP_201_CREATED,
            )
        return _error_response("validation_error", "Failed to create order", status.HTTP_400_BAD_REQUEST)
    except Exception as exc:
        return _error_response("http_error", str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
def orders_get(request, order_id: int):
    try:
        supabase = get_supabase()
        response = supabase.table("checkout_orders").select("*").eq("id", order_id).execute()
        if response.data:
            return Response(response.data[0])
        return _error_response("http_error", "Order not found", status.HTTP_404_NOT_FOUND)
    except Exception as exc:
        return _error_response("http_error", str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
def ai_recommendations(request):
    raw_limit = request.GET.get("limit", "6")
    category = request.GET.get("category")
    try:
        limit = int(raw_limit)
    except ValueError:
        return _error_response("validation_error", "limit must be a number", status.HTTP_400_BAD_REQUEST)

    try:
        return Response(recommend_products(limit=limit, category=category))
    except Exception as exc:
        return _error_response("http_error", str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)
