from datetime import date

from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from api.models import CheckoutOrder
from api.serializers import (
    AdminDatabaseSerializer,
    AdminReportsResponseSerializer,
    AdminSummarySerializer,
    AdminUsersResponseSerializer,
    CheckoutOrderCreateSerializer,
    CheckoutOrderSerializer,
    CustomerSummarySerializer,
    ProductCreateSerializer,
    ProductSerializer,
    ProducerOrdersResponseSerializer,
    ProducerPaymentsSerializer,
    ProducerProductsResponseSerializer,
    ProducerSummarySerializer,
    UserRegistrationSerializer,
    UserSerializer,
)
from app.core.security import ApiAuthError, issue_token, require_role, revoke_token, user_from_token
from app.repositories.auth_repo import find_user_by_email, verify_password
from app.services.ai_service import recommend_products
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


def _error_response(error: str, message: str, code: int) -> Response:
    return Response({"error": error, "message": message}, status=code)


def _auth_header(request) -> str | None:
    return request.META.get("HTTP_AUTHORIZATION")


def _require_user(request) -> dict | Response:
    try:
        return user_from_token(_auth_header(request))
    except ApiAuthError as exc:
        return _error_response(exc.error, exc.message, exc.status_code)


@api_view(["GET"])
def health(_request):
    return Response({"status": "ok"})


# ── Authentication ────────────────────────────────────────────────────────────

@csrf_exempt
@api_view(["POST"])
def auth_login(request):
    email = str(request.data.get("email", "")).strip()
    password = str(request.data.get("password", ""))

    if not email or not password:
        return _error_response("validation_error", "Email and password are required.", status.HTTP_400_BAD_REQUEST)

    user = find_user_by_email(email)
    if not user or not verify_password(password, user):
        return _error_response("unauthenticated", "Invalid email or password.", status.HTTP_401_UNAUTHORIZED)

    token = issue_token(user)
    return Response({
        "access_token": token,
        "token_type": "bearer",
        "user": UserSerializer(user).data,
    })


@csrf_exempt
@api_view(["POST"])
def auth_register(request):
    serializer = UserRegistrationSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"error": "validation_error", "message": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    if find_user_by_email(serializer.validated_data["email"]):
        return _error_response("validation_error", "User already exists.", status.HTTP_400_BAD_REQUEST)

    user = serializer.save()
    return Response(
        {"message": "User registered successfully.", "user": UserSerializer(user).data},
        status=status.HTTP_201_CREATED,
    )


@csrf_exempt
@api_view(["POST"])
def auth_logout(request):
    try:
        revoke_token(_auth_header(request))
        return Response({"message": "Logged out successfully."})
    except ApiAuthError as exc:
        return _error_response(exc.error, exc.message, exc.status_code)


# ── Dashboard — shared ────────────────────────────────────────────────────────

@api_view(["GET"])
def dashboards_me(request):
    user = _require_user(request)
    if isinstance(user, Response):
        return user
    return Response(user)


# ── Dashboard — Producer ──────────────────────────────────────────────────────

@api_view(["GET"])
def dashboards_producer(request):
    user = _require_user(request)
    if isinstance(user, Response):
        return user
    try:
        require_role(user, ["producer"])
        return Response(ProducerSummarySerializer(producer_summary(user)).data)
    except ApiAuthError as exc:
        return _error_response(exc.error, exc.message, exc.status_code)


@api_view(["GET"])
def dashboards_producer_products(request):
    user = _require_user(request)
    if isinstance(user, Response):
        return user
    try:
        require_role(user, ["producer"])
        return Response(ProducerProductsResponseSerializer(producer_products(user)).data)
    except ApiAuthError as exc:
        return _error_response(exc.error, exc.message, exc.status_code)


@api_view(["GET"])
def dashboards_producer_orders(request):
    user = _require_user(request)
    if isinstance(user, Response):
        return user
    try:
        require_role(user, ["producer"])
        return Response(ProducerOrdersResponseSerializer(producer_orders(user)).data)
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
    except ApiAuthError as exc:
        return _error_response(exc.error, exc.message, exc.status_code)

    serializer = ProductCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"error": "validation_error", "message": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    try:
        product = create_producer_product(user, serializer.validated_data)
        return Response({"message": "Product created.", "data": product}, status=status.HTTP_201_CREATED)
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
    except ApiAuthError as exc:
        return _error_response(exc.error, exc.message, exc.status_code)

    serializer = ProductSerializer(data=request.data, partial=True)
    if not serializer.is_valid():
        return Response({"error": "validation_error", "message": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    try:
        product = update_producer_product(user, product_id, request.data)
        return Response({"message": "Product updated.", "data": product})
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
        return Response(ProducerPaymentsSerializer(producer_payments(user)).data)
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
        return Response({"message": "Order status updated.", "data": result})
    except ApiAuthError as exc:
        return _error_response(exc.error, exc.message, exc.status_code)
    except LookupError as exc:
        return _error_response("not_found", str(exc), status.HTTP_404_NOT_FOUND)
    except ValueError as exc:
        return _error_response("validation_error", str(exc), status.HTTP_400_BAD_REQUEST)


# ── Dashboard — Admin ─────────────────────────────────────────────────────────

@api_view(["GET"])
def dashboards_admin(request):
    user = _require_user(request)
    if isinstance(user, Response):
        return user
    try:
        require_role(user, ["admin"])
        return Response(AdminSummarySerializer(admin_summary(user)).data)
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
        if date_from:
            date.fromisoformat(date_from)
        if date_to:
            date.fromisoformat(date_to)
        if date_from and date_to and date_from > date_to:
            return _error_response("validation_error", "from must be before to.", status.HTTP_400_BAD_REQUEST)
        return Response(AdminReportsResponseSerializer(admin_reports(user, date_from=date_from, date_to=date_to)).data)
    except ValueError:
        return _error_response("validation_error", "Dates must use YYYY-MM-DD.", status.HTTP_400_BAD_REQUEST)
    except ApiAuthError as exc:
        return _error_response(exc.error, exc.message, exc.status_code)


@api_view(["GET"])
def admin_commission(request):
    user = _require_user(request)
    if isinstance(user, Response):
        return user
    try:
        require_role(user, ["admin"])
        date_from = request.GET.get("from")
        date_to = request.GET.get("to")
        if date_from:
            date.fromisoformat(date_from)
        if date_to:
            date.fromisoformat(date_to)
        if date_from and date_to and date_from > date_to:
            return _error_response("validation_error", "from must be before to.", status.HTTP_400_BAD_REQUEST)
        return Response(AdminReportsResponseSerializer(admin_reports(user, date_from=date_from, date_to=date_to)).data)
    except ValueError:
        return _error_response("validation_error", "Dates must use YYYY-MM-DD.", status.HTTP_400_BAD_REQUEST)
    except ApiAuthError as exc:
        return _error_response(exc.error, exc.message, exc.status_code)


@api_view(["GET"])
def dashboards_admin_users(request):
    user = _require_user(request)
    if isinstance(user, Response):
        return user
    try:
        require_role(user, ["admin"])
        return Response(AdminUsersResponseSerializer(admin_users(user)).data)
    except ApiAuthError as exc:
        return _error_response(exc.error, exc.message, exc.status_code)


@api_view(["GET"])
def dashboards_admin_database(request):
    user = _require_user(request)
    if isinstance(user, Response):
        return user
    try:
        require_role(user, ["admin"])
        return Response(AdminDatabaseSerializer(admin_database(user)).data)
    except ApiAuthError as exc:
        return _error_response(exc.error, exc.message, exc.status_code)


# ── Dashboard — Customer ──────────────────────────────────────────────────────

@api_view(["GET"])
def dashboards_customer(request):
    user = _require_user(request)
    if isinstance(user, Response):
        return user
    try:
        require_role(user, ["customer"])
        return Response(CustomerSummarySerializer(customer_summary(user)).data)
    except ApiAuthError as exc:
        return _error_response(exc.error, exc.message, exc.status_code)


# ── Orders (Checkout) ─────────────────────────────────────────────────────────

@csrf_exempt
@api_view(["POST"])
def orders_create(request):
    serializer = CheckoutOrderCreateSerializer(data={
        "full_name": request.data.get("fullName"),
        "email": request.data.get("email"),
        "address": request.data.get("address"),
        "city": request.data.get("city"),
        "postal_code": request.data.get("postalCode"),
        "payment_method": request.data.get("paymentMethod"),
    })
    if not serializer.is_valid():
        return Response({"error": "validation_error", "message": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    order = serializer.save()
    return Response(
        {"id": order.id, "message": "Order created successfully.", "data": CheckoutOrderSerializer(order).data},
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
def orders_get(request, order_id: int):
    try:
        order = CheckoutOrder.objects.get(id=order_id)
        return Response(CheckoutOrderSerializer(order).data)
    except CheckoutOrder.DoesNotExist:
        return _error_response("not_found", "Order not found.", status.HTTP_404_NOT_FOUND)


# ── AI Recommendations ────────────────────────────────────────────────────────

@api_view(["GET"])
def ai_recommendations(request):
    raw_limit = request.GET.get("limit", "6")
    category = request.GET.get("category")
    try:
        limit = int(raw_limit)
    except ValueError:
        return _error_response("validation_error", "limit must be a number.", status.HTTP_400_BAD_REQUEST)

    try:
        return Response(recommend_products(limit=limit, category=category))
    except Exception as exc:
        return _error_response("http_error", str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)
