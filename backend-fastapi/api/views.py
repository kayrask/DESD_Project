from datetime import date

from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from api.models import CheckoutOrder, CommissionReport, Order, OrderItem, Product, User
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


def _error_response(error: str, message: str, code: int) -> Response:
    return Response({"error": error, "message": message}, status=code)


def _auth_header(request) -> str | None:
    return request.META.get("HTTP_AUTHORIZATION")


def _require_user(request) -> dict | Response:
    try:
        return user_from_token(_auth_header(request))
    except ApiAuthError as exc:
        return _error_response(exc.error, exc.message, exc.status_code)


def _get_producer_user(email: str) -> User:
    try:
        return User.objects.get(email=email, role="producer")
    except User.DoesNotExist:
        raise LookupError("Producer account not found")


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
    return Response({"access_token": token, "token_type": "bearer", "user": UserSerializer(user).data})


@csrf_exempt
@api_view(["POST"])
def auth_register(request):
    serializer = UserRegistrationSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"error": "validation_error", "message": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    if find_user_by_email(serializer.validated_data["email"]):
        return _error_response("validation_error", "User already exists.", status.HTTP_400_BAD_REQUEST)
    user = serializer.save()
    return Response({"message": "User registered successfully.", "user": UserSerializer(user).data}, status=status.HTTP_201_CREATED)


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
        producer = _get_producer_user(user["email"])
        today = date.today()
        summary = {
            "orders_today": Order.objects.filter(producer=producer, delivery_date=today).count(),
            "low_stock_products": Product.objects.filter(producer=producer, stock__lt=10).count(),
            "quick_links": ["products", "orders", "payments"],
        }
        return Response(ProducerSummarySerializer(summary).data)
    except ApiAuthError as exc:
        return _error_response(exc.error, exc.message, exc.status_code)


@api_view(["GET"])
def dashboards_producer_products(request):
    user = _require_user(request)
    if isinstance(user, Response):
        return user
    try:
        require_role(user, ["producer"])
        producer = _get_producer_user(user["email"])
        items = list(
            Product.objects.filter(producer=producer)
            .order_by("name")
            .values("id", "name", "category", "price", "stock", "status")
        )
        for p in items:
            p["price"] = float(p["price"])
        return Response(ProducerProductsResponseSerializer({"items": items}).data)
    except ApiAuthError as exc:
        return _error_response(exc.error, exc.message, exc.status_code)


@api_view(["GET"])
def dashboards_producer_orders(request):
    user = _require_user(request)
    if isinstance(user, Response):
        return user
    try:
        require_role(user, ["producer"])
        producer = _get_producer_user(user["email"])
        items = [
            {
                "order_id": o.order_id,
                "customer": o.customer_name,
                "delivery": o.delivery_date.isoformat() if o.delivery_date else None,
                "status": o.status,
            }
            for o in Order.objects.filter(producer=producer).order_by("delivery_date")
        ]
        return Response(ProducerOrdersResponseSerializer({"items": items}).data)
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
        producer = _get_producer_user(user["email"])
        data = serializer.validated_data
        stock = int(data.get("stock", 0))
        prod_status = data.get("status", "Available") if stock > 0 else "Out of Stock"
        product = Product.objects.create(
            name=str(data["name"]).strip(),
            category=str(data["category"]).strip(),
            price=round(float(data["price"]), 2),
            stock=stock,
            status=prod_status,
            producer=producer,
        )
        return Response(
            {"message": "Product created.", "data": ProductSerializer(product).data},
            status=status.HTTP_201_CREATED,
        )
    except (ValueError, LookupError) as exc:
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

    try:
        producer = _get_producer_user(user["email"])
        product = Product.objects.get(id=product_id)
        if product.producer_id != producer.id:
            return _error_response("forbidden", "You can only edit your own products.", status.HTTP_403_FORBIDDEN)
        for field in ("name", "category", "status"):
            if field in request.data:
                setattr(product, field, str(request.data[field]).strip())
        if "price" in request.data:
            product.price = round(float(request.data["price"]), 2)
        if "stock" in request.data:
            product.stock = int(request.data["stock"])
        if product.stock == 0:
            product.status = "Out of Stock"
        elif product.status.lower() == "out of stock" and product.stock > 0:
            product.status = "Available"
        product.save()
        return Response({"message": "Product updated.", "data": ProductSerializer(product).data})
    except Product.DoesNotExist:
        return _error_response("not_found", "Product not found.", status.HTTP_404_NOT_FOUND)
    except (ValueError, TypeError) as exc:
        return _error_response("validation_error", str(exc), status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
def dashboards_producer_payments(request):
    user = _require_user(request)
    if isinstance(user, Response):
        return user
    try:
        require_role(user, ["producer"])
        producer = _get_producer_user(user["email"])
        delivered_items = OrderItem.objects.filter(
            order__producer=producer, order__status="Delivered"
        )
        gross = sum(float(i.unit_price) * i.quantity for i in delivered_items)
        payments = {
            "this_week": round(gross, 2),
            "pending": round(gross * 0.20, 2),
            "commission": round(gross * 0.10, 2),
        }
        return Response(ProducerPaymentsSerializer(payments).data)
    except ApiAuthError as exc:
        return _error_response(exc.error, exc.message, exc.status_code)


@api_view(["GET"])
def producer_order_get(request, order_id: str):
    user = _require_user(request)
    if isinstance(user, Response):
        return user
    try:
        require_role(user, ["producer"])
        producer = _get_producer_user(user["email"])
        order = Order.objects.get(order_id=order_id, producer=producer)
        items = [
            {
                "id": item.id,
                "product_id": item.product_id,
                "name": item.product.name,
                "quantity": item.quantity,
                "unit_price": float(item.unit_price),
                "line_total": round(item.quantity * float(item.unit_price), 2),
            }
            for item in order.items.select_related("product").order_by("id")
        ]
        return Response({
            "id": order.id,
            "order_id": order.order_id,
            "customer": order.customer_name,
            "delivery": order.delivery_date.isoformat() if order.delivery_date else None,
            "status": order.status,
            "items": items,
            "order_total": round(sum(i["line_total"] for i in items), 2),
        })
    except ApiAuthError as exc:
        return _error_response(exc.error, exc.message, exc.status_code)
    except Order.DoesNotExist:
        return _error_response("not_found", "Order not found.", status.HTTP_404_NOT_FOUND)


@csrf_exempt
@api_view(["PATCH"])
def producer_order_status_update(request, order_id: str):
    user = _require_user(request)
    if isinstance(user, Response):
        return user
    _transitions = {"pending": "confirmed", "confirmed": "ready", "ready": "delivered"}
    try:
        require_role(user, ["producer"])
        producer = _get_producer_user(user["email"])
        new_status = str(request.data.get("status", "")).strip().lower()
        order = Order.objects.get(order_id=order_id, producer=producer)
        current = order.status.strip().lower()
        if _transitions.get(current) != new_status:
            return _error_response("validation_error", f"Cannot move from {current} to {new_status}.", status.HTTP_400_BAD_REQUEST)
        order.status = new_status.capitalize()
        order.save()
        return Response({"message": "Order status updated.", "data": {"order_id": order.order_id, "status": order.status}})
    except ApiAuthError as exc:
        return _error_response(exc.error, exc.message, exc.status_code)
    except Order.DoesNotExist:
        return _error_response("not_found", "Order not found.", status.HTTP_404_NOT_FOUND)
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
        from django.db.models import Sum
        from api.models import QualityAssessment
        commission_today = CommissionReport.objects.filter(
            report_date=date.today()
        ).aggregate(total=Sum("commission_amount"))["total"] or 0
        summary = {
            "commission_today": round(float(commission_today), 2),
            "active_users": User.objects.filter(status="active").count(),
            "open_flags": QualityAssessment.objects.filter(model_confidence__lt=0.60).count(),
        }
        return Response(AdminSummarySerializer(summary).data)
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
        qs = CommissionReport.objects.all()
        if date_from:
            qs = qs.filter(report_date__gte=date_from)
        if date_to:
            qs = qs.filter(report_date__lte=date_to)
        rows = [{"date": str(r.report_date), "orders": r.total_orders, "gross": float(r.gross_amount), "commission": float(r.commission_amount)} for r in qs]
        return Response(AdminReportsResponseSerializer({"rows": rows}).data)
    except ValueError:
        return _error_response("validation_error", "Dates must use YYYY-MM-DD.", status.HTTP_400_BAD_REQUEST)
    except ApiAuthError as exc:
        return _error_response(exc.error, exc.message, exc.status_code)


@api_view(["GET"])
def admin_commission(request):
    return dashboards_admin_reports(request)


@api_view(["GET"])
def dashboards_admin_users(request):
    user = _require_user(request)
    if isinstance(user, Response):
        return user
    try:
        require_role(user, ["admin"])
        items = [
            {"email": u.email, "role": u.role.capitalize(), "status": u.status.capitalize()}
            for u in User.objects.all().order_by("email")
        ]
        return Response(AdminUsersResponseSerializer({"items": items}).data)
    except ApiAuthError as exc:
        return _error_response(exc.error, exc.message, exc.status_code)


@api_view(["GET"])
def dashboards_admin_database(request):
    user = _require_user(request)
    if isinstance(user, Response):
        return user
    try:
        require_role(user, ["admin"])
        users = list(User.objects.values("id", "email", "role", "full_name", "status").order_by("id"))
        products = [
            {**p, "price": float(p["price"])}
            for p in Product.objects.values("id", "name", "category", "price", "stock", "status", "producer_id").order_by("id")
        ]
        orders = [
            {**o, "delivery_date": str(o["delivery_date"]) if o["delivery_date"] else None}
            for o in Order.objects.values("id", "order_id", "customer_name", "delivery_date", "status", "producer_id").order_by("id")
        ]
        return Response(AdminDatabaseSerializer({"users": users, "products": products, "orders": orders}).data)
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
        summary = {"upcoming_deliveries": 2, "saved_producers": 4}
        return Response(CustomerSummarySerializer(summary).data)
    except ApiAuthError as exc:
        return _error_response(exc.error, exc.message, exc.status_code)


# ── Orders ────────────────────────────────────────────────────────────────────

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


# ── AI ────────────────────────────────────────────────────────────────────────

@api_view(["GET"])
def ai_recommendations(request):
    try:
        limit = int(request.GET.get("limit", "6"))
    except ValueError:
        return _error_response("validation_error", "limit must be a number.", status.HTTP_400_BAD_REQUEST)
    try:
        return Response(recommend_products(
            limit=limit,
            category=request.GET.get("category"),
            customer_email=request.GET.get("customer_email"),
        ))
    except Exception as exc:
        return _error_response("http_error", str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["POST"])
def ai_quality_check(request):
    from app.services.quality_service import assess_product_image
    try:
        user_data = user_from_token(request)
    except ApiAuthError as exc:
        return _error_response("auth_error", str(exc), status.HTTP_401_UNAUTHORIZED)
    if user_data.get("role") != "producer":
        return _error_response("forbidden", "Only producers can run quality checks.", status.HTTP_403_FORBIDDEN)
    product_id = request.data.get("product_id")
    image_file = request.FILES.get("image")
    if not product_id or not image_file:
        return _error_response("validation_error", "product_id and image are required.", status.HTTP_400_BAD_REQUEST)
    try:
        producer = User.objects.get(email=user_data["email"])
        result = assess_product_image(image_file, int(product_id), producer)
        return Response(result)
    except Exception as exc:
        return _error_response("http_error", str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)
