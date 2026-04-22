"""
Django template-based views (MVT pattern).

Models  → api/models.py
Views   → here (class-based views using Django ORM directly)
Templates → api/templates/
"""

from datetime import date, datetime as _dt, timedelta
from decimal import Decimal
import csv
import pathlib
from collections import defaultdict

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from django.views.generic import ListView, TemplateView

from api.forms import (
    CheckoutForm,
    LoginForm,
    OrderStatusForm,
    ProductForm,
    ReportFilterForm,
    RegisterForm,
    ReviewForm,
)
from api.models import (
    CartReservation,
    CommissionReport,
    Order,
    OrderItem,
    Product,
    QualityAssessment,
    CheckoutOrder,
    Review,
    User,
)
from app.services.ai_service import recommend_products
from app.services.quality_service import (
    assess_product_image,
    get_ai_monitoring_stats,
    get_producer_assessments,
)


# ── Cart reservation helpers ─────────────────────────────────────────────────

_RESERVATION_TTL_HOURS = 2  # reservations older than this are ignored


def _reserved_by_others(product_id, session_key):
    """Return total units of a product reserved in other active sessions."""
    cutoff = timezone.now() - timedelta(hours=_RESERVATION_TTL_HOURS)
    return (
        CartReservation.objects
        .filter(product_id=product_id, updated_at__gte=cutoff)
        .exclude(session_key=session_key)
        .aggregate(total=Sum("quantity"))["total"] or 0
    )


def _available_stock(product, session_key):
    """Effective stock available for this session (real stock minus other carts)."""
    return max(0, product.stock - _reserved_by_others(product.id, session_key))


def _upsert_reservation(session_key, product_id, quantity):
    if quantity > 0:
        CartReservation.objects.update_or_create(
            session_key=session_key,
            product_id=product_id,
            defaults={"quantity": quantity},
        )
    else:
        CartReservation.objects.filter(session_key=session_key, product_id=product_id).delete()


def _clear_reservations(session_key):
    CartReservation.objects.filter(session_key=session_key).delete()


def _ensure_session_key(request):
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key


# ── Real-time broadcast helpers (Channels) ───────────────────────────────────

def _get_channel_layer():
    from channels.layers import get_channel_layer
    return get_channel_layer()


def _broadcast_order_status(order):
    """Notify customer WebSocket connections about an order status change."""
    from asgiref.sync import async_to_sync
    layer = _get_channel_layer()
    if layer is None:
        return
    payload = {"type": "order.status.update", "order_id": order.order_id, "status": order.status}
    # Notify anyone watching this specific order (order confirmation page)
    async_to_sync(layer.group_send)(f"order_{order.order_id}", payload)
    # Notify the customer's dashboard notification channel
    try:
        parts = order.order_id.split("-")  # CO-1 or CO-1-42
        checkout_id = int(parts[1])
        from api.models import CheckoutOrder
        co = CheckoutOrder.objects.filter(id=checkout_id).select_related("customer").first()
        if co and co.customer_id:
            async_to_sync(layer.group_send)(f"user_{co.customer_id}", payload)
    except (IndexError, ValueError):
        pass


def _broadcast_stock_update(product):
    """Notify all product-list pages about a stock change."""
    from asgiref.sync import async_to_sync
    layer = _get_channel_layer()
    if layer is None:
        return
    async_to_sync(layer.group_send)(
        "stock_updates",
        {"type": "stock.update", "product_id": product.id, "stock": product.stock, "status": product.status},
    )


# ── Role-enforcement mixins ───────────────────────────────────────────────────

def _is_ajax(request):
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


class _RoleMixin(LoginRequiredMixin, UserPassesTestMixin):
    login_url = "/login/"
    _required_role: str = ""

    def test_func(self):
        return self.request.user.role == self._required_role

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            # AJAX callers get a JSON 401; browser clients get login redirect
            # with ?next= so they land back after authentication.
            if _is_ajax(self.request):
                return JsonResponse(
                    {"error": "unauthenticated", "message": "Authentication required."},
                    status=401,
                )
            return redirect(f"/login/?next={self.request.path}")
        # Authenticated but wrong role → 403
        if _is_ajax(self.request):
            return JsonResponse(
                {"error": "forbidden", "message": "You do not have permission to access this page."},
                status=403,
            )
        return redirect("/403/")


class CustomerRequiredMixin(_RoleMixin):
    _required_role = "customer"


class ProducerRequiredMixin(_RoleMixin):
    _required_role = "producer"


class AdminRequiredMixin(_RoleMixin):
    _required_role = "admin"


# ── Public views ──────────────────────────────────────────────────────────────

class HomeView(TemplateView):
    template_name = "home.html"


class MarketplaceView(ListView):
    template_name = "marketplace.html"
    context_object_name = "products"
    paginate_by = 12

    _visible = ("Available", "In Season")

    def get_queryset(self):
        qs = Product.objects.filter(status__in=self._visible).select_related("producer")
        q = self.request.GET.get("q", "").strip()
        category = self.request.GET.get("category", "").strip()
        organic = self.request.GET.get("organic", "")
        allergen_free = self.request.GET.get("allergen_free", "")
        if q:
            qs = qs.filter(
                Q(name__icontains=q) |
                Q(description__icontains=q) |
                Q(producer__full_name__icontains=q)
            )
        if category:
            qs = qs.filter(category=category)
        if organic:
            qs = qs.filter(is_organic=True)
        if allergen_free:
            qs = qs.filter(Q(allergens="") | Q(allergens__isnull=True))
        return qs.order_by("name")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        raw = (
            Product.objects.filter(status__in=self._visible)
            .exclude(category__isnull=True)
            .exclude(category="")
            .values_list("category", flat=True)
        )
        ctx["categories"] = sorted(set(c.strip() for c in raw))
        ctx["q"] = self.request.GET.get("q", "")
        ctx["selected_category"] = self.request.GET.get("category", "")
        ctx["organic_filter"] = self.request.GET.get("organic", "")
        ctx["allergen_free_filter"] = self.request.GET.get("allergen_free", "")

        customer_email = None
        if self.request.user.is_authenticated and self.request.user.role == "customer":
            customer_email = self.request.user.email

        try:
            recs = recommend_products(limit=4, customer_email=customer_email)
            items = recs.get("items", []) or []
            rec_ids = [i.get("id") for i in items if isinstance(i, dict) and isinstance(i.get("id"), int)]
            prod_name_by_id = {
                p.id: (p.producer.full_name or p.producer.email)
                for p in Product.objects.filter(id__in=rec_ids).select_related("producer")
            }
            for i in items:
                if isinstance(i, dict) and isinstance(i.get("id"), int):
                    i["producer_name"] = prod_name_by_id.get(i["id"], "")
            ctx["recommendations"] = items
            ctx["rec_model_version"] = recs.get("model_version", "")
        except Exception:
            ctx["recommendations"] = []
            ctx["rec_model_version"] = ""
        return ctx


class ForProducersView(TemplateView):
    template_name = "for_producers.html"


class HowItWorksView(TemplateView):
    template_name = "how_it_works.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["steps"] = [
            {"title": "Browse Products", "desc": "Explore fresh produce from verified local producers in your area."},
            {"title": "Add to Cart", "desc": "Choose what you want and add it to your cart with a single click."},
            {"title": "Place Your Order", "desc": "Complete checkout with your delivery details and preferred payment method."},
            {"title": "Receive Delivery", "desc": "Your producer confirms and delivers directly to your door."},
        ]
        return ctx


class SustainabilityView(TemplateView):
    template_name = "sustainability.html"


class LegalView(TemplateView):
    template_name = "legal.html"


# ── Authentication ────────────────────────────────────────────────────────────

class LoginPageView(View):
    template_name = "login.html"

    def get(self, request):
        if request.user.is_authenticated:
            return redirect(request.GET.get("next", "/"))
        # Show session-expired message only when explicitly triggered by the
        # JS countdown timer (?expired=1), not every ?next= redirect.
        if request.GET.get("expired") == "1":
            messages.warning(request, "Your session has expired. Please log in again.")
        return render(request, self.template_name, {"form": LoginForm()})

    def post(self, request):
        form = LoginForm(request.POST)
        if form.is_valid():
            user = authenticate(
                request,
                username=form.cleaned_data["email"],
                password=form.cleaned_data["password"],
            )
            if user is not None:
                login(request, user)
                messages.success(request, f"Welcome back, {user.full_name}!")
                next_url = request.GET.get("next", "/")
                # Guard against open-redirect: only allow relative paths.
                if not next_url.startswith("/"):
                    next_url = "/"
                return redirect(next_url)
            form.add_error(None, "Invalid email or password.")
        return render(request, self.template_name, {"form": form})


class LogoutView(View):
    def post(self, request):
        logout(request)
        messages.info(request, "You have been logged out.")
        return redirect("/login/")


class RegisterPageView(View):
    template_name = "register.html"

    def get(self, request):
        if request.user.is_authenticated:
            return redirect("/")
        return render(request, self.template_name, {"form": RegisterForm()})

    def post(self, request):
        form = RegisterForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            if User.objects.filter(email=email).exists():
                form.add_error("email", "An account with this email already exists.")
                return render(request, self.template_name, {"form": form})
            User.objects.create_user(
                email=email,
                password=form.cleaned_data["password"],
                full_name=form.cleaned_data["full_name"],
                role=form.cleaned_data["role"],
            )
            messages.success(request, "Account created! You can now log in.")
            return redirect("/login/")
        return render(request, self.template_name, {"form": form})


# ── Customer views ────────────────────────────────────────────────────────────

class CustomerDashboardView(CustomerRequiredMixin, ListView):
    template_name = "customer/dashboard.html"
    context_object_name = "orders"
    paginate_by = 10

    def get_queryset(self):
        qs = CheckoutOrder.objects.filter(customer=self.request.user).order_by("-created_at")
        status_filter = self.request.GET.get("status", "")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        ctx["upcoming_deliveries"] = CheckoutOrder.objects.filter(
            customer=user,
            status__in=["pending", "confirmed"],
        ).count()
        ctx["total_orders"] = CheckoutOrder.objects.filter(customer=user).count()
        ctx["status_filter"] = self.request.GET.get("status", "")
        return ctx


class CustomerOrdersView(CustomerRequiredMixin, View):
    """Redirects to the dashboard which now contains the full order history."""
    def get(self, request):
        return redirect("customer_dashboard")


def product_suggest(request):
    """Return up to 8 available products matching the query — used for live search autocomplete."""
    q = request.GET.get("q", "").strip()
    if len(q) < 2:
        return JsonResponse({"results": []})
    qs = (
        Product.objects.filter(
            Q(name__icontains=q) | Q(description__icontains=q) | Q(producer__full_name__icontains=q),
            status="Available",
        )
        .values("id", "name", "category", "price")[:8]
    )
    return JsonResponse({"results": list(qs)})


class ProductListView(View):
    """Redirects to marketplace — kept for URL backwards-compatibility only."""
    def get(self, request):
        qs = request.GET.urlencode()
        url = "/marketplace/" + (f"?{qs}" if qs else "")
        return redirect(url)


class ProductDetailView(View):
    template_name = "customer/product_detail.html"

    def _context(self, request, pk, form=None):
        product = get_object_or_404(Product, pk=pk)
        reviews = product.reviews.select_related("customer").all()
        avg_rating = None
        if reviews:
            avg_rating = round(sum(r.rating for r in reviews) / len(reviews), 1)
        existing_review = None
        if request.user.is_authenticated:
            existing_review = reviews.filter(customer=request.user).first()
        return {
            "product": product,
            "reviews": reviews,
            "avg_rating": avg_rating,
            "review_form": form or ReviewForm(),
            "existing_review": existing_review,
            "star_range": range(1, 6),
        }

    def get(self, request, pk):
        return render(request, self.template_name, self._context(request, pk))

    def post(self, request, pk):
        if not request.user.is_authenticated or request.user.role != "customer":
            return redirect("login")
        product = get_object_or_404(Product, pk=pk)
        existing = Review.objects.filter(product=product, customer=request.user).first()
        if existing:
            messages.warning(request, "You have already reviewed this product.")
            return redirect("product_detail", pk=pk)
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.product = product
            review.customer = request.user
            review.save()
            messages.success(request, "Review submitted. Thank you!")
            return redirect("product_detail", pk=pk)
        return render(request, self.template_name, self._context(request, pk, form=form))


class CartView(CustomerRequiredMixin, TemplateView):
    template_name = "customer/cart.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        cart = self.request.session.get("cart", [])
        # Add pre-computed line_total to each item so templates don't need widthratio.
        for item in cart:
            item["line_total"] = round(float(item["price"]) * int(item["quantity"]), 2)
        ctx["cart"] = cart
        ctx["total"] = round(sum(i["line_total"] for i in cart), 2)
        return ctx


class AddToCartView(CustomerRequiredMixin, View):
    def post(self, request, product_id):
        is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
        next_url = request.POST.get("next") or request.GET.get("next") or "/products/"
        session_key = _ensure_session_key(request)
        try:
            quantity = max(1, int(request.POST.get("quantity", 1)))
        except (ValueError, TypeError):
            quantity = 1
        with transaction.atomic():
            product = get_object_or_404(
                Product.objects.select_for_update().select_related("producer"),
                pk=product_id,
                status__in=("Available", "In Season"),
            )
            available = _available_stock(product, session_key)
            quantity = min(quantity, available)
            cart = request.session.get("cart", [])
            for item in cart:
                if item["product_id"] == product_id:
                    new_qty = item["quantity"] + quantity
                    if new_qty > available:
                        msg = f"Only {available} unit(s) of {product.name} available."
                        if is_ajax:
                            return JsonResponse({"ok": False, "message": msg})
                        messages.error(request, msg)
                        return redirect(next_url)
                    item["quantity"] = new_qty
                    request.session["cart"] = cart
                    _upsert_reservation(session_key, product_id, new_qty)
                    msg = f"Updated {product.name} quantity in cart."
                    if is_ajax:
                        return JsonResponse({"ok": True, "message": msg, "cart_count": len(cart)})
                    messages.success(request, msg)
                    return redirect(next_url)
            if available < 1:
                msg = f"{product.name} is not available right now."
                if is_ajax:
                    return JsonResponse({"ok": False, "message": msg})
                messages.error(request, msg)
                return redirect(next_url)
            cart.append({
                "product_id": product_id,
                "name": product.name,
                "price": float(product.price),
                "quantity": quantity,
                "producer_id": product.producer_id,
                "producer_name": product.producer.full_name,
            })
            request.session["cart"] = cart
            _upsert_reservation(session_key, product_id, quantity)
        msg = f"{quantity}× {product.name} added to cart."
        if is_ajax:
            return JsonResponse({"ok": True, "message": msg, "cart_count": len(request.session.get("cart", []))})
        messages.success(request, msg)
        return redirect(next_url)


class RemoveFromCartView(CustomerRequiredMixin, View):
    def post(self, request, product_id):
        session_key = _ensure_session_key(request)
        cart = request.session.get("cart", [])
        request.session["cart"] = [i for i in cart if i["product_id"] != product_id]
        _upsert_reservation(session_key, product_id, 0)
        messages.info(request, "Item removed from cart.")
        return redirect("/cart/")


class UpdateCartView(CustomerRequiredMixin, View):
    def post(self, request, product_id):
        try:
            quantity = int(request.POST.get("quantity", 1))
        except (ValueError, TypeError):
            quantity = 1
        if quantity < 1:
            quantity = 1
        session_key = _ensure_session_key(request)
        with transaction.atomic():
            product = get_object_or_404(Product.objects.select_for_update(), pk=product_id)
            available = _available_stock(product, session_key)
            if quantity > available:
                messages.error(
                    request,
                    f"Only {available} unit(s) of {product.name} available right now.",
                )
                return redirect("/cart/")
            cart = request.session.get("cart", [])
            for item in cart:
                if item["product_id"] == product_id:
                    item["quantity"] = quantity
                    break
            request.session["cart"] = cart
            _upsert_reservation(session_key, product_id, quantity)
        messages.success(request, "Cart updated.")
        return redirect("/cart/")


class CheckoutView(CustomerRequiredMixin, View):
    template_name = "customer/checkout.html"

    _commission_rate = Decimal("0.05")

    def _build_context(self, request, form, cart, product_by_id=None, producer_errors=None):
        # Load products from DB if not already provided (needed for producer grouping).
        if cart and product_by_id is None:
            pids = [int(i["product_id"]) for i in cart if str(i.get("product_id", "")).isdigit()]
            products = Product.objects.filter(pk__in=pids).select_related("producer")
            product_by_id = {p.id: p for p in products}

        # Group cart items by producer, calculating per-producer subtotals and commission.
        producer_groups_map: dict[int, dict] = {}
        for item in cart:
            pid_str = str(item.get("product_id", ""))
            if not pid_str.isdigit():
                continue
            product = (product_by_id or {}).get(int(pid_str))
            # Prefer live DB data; fall back to stored session data for old sessions.
            producer_id = product.producer_id if product else item.get("producer_id", 0)
            producer_name = (
                product.producer.full_name if product else item.get("producer_name", "Unknown Producer")
            )
            qty = int(item["quantity"])
            line_total = round(float(item["price"]) * qty, 2)
            if producer_id not in producer_groups_map:
                producer_groups_map[producer_id] = {
                    "producer_id": producer_id,
                    "producer_name": producer_name,
                    "items": [],
                    "subtotal": Decimal("0"),
                }
            producer_groups_map[producer_id]["items"].append({**item, "line_total": line_total})
            producer_groups_map[producer_id]["subtotal"] += Decimal(str(item["price"])) * qty

        producer_groups = []
        for g in producer_groups_map.values():
            sub = g["subtotal"]
            g["subtotal"] = float(sub.quantize(Decimal("0.01")))
            g["commission"] = float((sub * self._commission_rate).quantize(Decimal("0.01")))
            producer_groups.append(g)

        total = round(sum(float(i["price"]) * int(i["quantity"]) for i in cart), 2)
        commission = round(total * float(self._commission_rate), 2)
        min_delivery_date = (date.today() + timedelta(days=2)).isoformat()

        return {
            "form": form,
            "cart": cart,
            "total": total,
            "commission": commission,
            "producer_groups": producer_groups,
            "min_delivery_date": min_delivery_date,
            "producer_errors": producer_errors or [],
        }

    def get(self, request):
        cart = request.session.get("cart", [])
        form = CheckoutForm(initial={"email": request.user.email})
        return render(request, self.template_name, self._build_context(request, form, cart))

    def post(self, request):
        form = CheckoutForm(request.POST)
        cart = request.session.get("cart", [])

        if not cart:
            messages.error(request, "Your cart is empty.")
            return redirect("/cart/")

        # Address must be selected from Nominatim suggestions.
        if request.POST.get("address_confirmed") != "1":
            messages.error(request, "Please select a valid address from the suggestions.")
            return render(request, self.template_name, self._build_context(request, form, cart))

        if not form.is_valid():
            return render(request, self.template_name, self._build_context(request, form, cart))

        # Parse and validate per-producer delivery dates submitted as
        # delivery_date_<producer_id> fields from the order summary column.
        min_date = date.today() + timedelta(days=2)
        producer_delivery_dates: dict[int, date] = {}
        date_errors: list[str] = []
        for key, value in request.POST.items():
            if not key.startswith("delivery_date_"):
                continue
            suffix = key[len("delivery_date_"):]
            if not suffix.isdigit():
                continue
            try:
                parsed = _dt.strptime(value, "%Y-%m-%d").date()
                if parsed < min_date:
                    date_errors.append(
                        "Each delivery date must be at least 2 days from today."
                    )
                else:
                    producer_delivery_dates[int(suffix)] = parsed
            except ValueError:
                date_errors.append("Invalid delivery date — please select a valid date.")

        if date_errors:
            # De-duplicate messages
            for err in dict.fromkeys(date_errors):
                messages.error(request, err)
            return render(request, self.template_name, self._build_context(request, form, cart))

        with transaction.atomic():
            # Lock product rows so two concurrent checkouts cannot both read the
            # same stock and oversell.
            product_ids = [
                int(i["product_id"]) for i in cart if str(i.get("product_id", "")).isdigit()
            ]
            products = list(
                Product.objects.select_for_update()
                .filter(pk__in=product_ids)
                .select_related("producer")
            )
            product_by_id = {p.id: p for p in products}

            # Stock validation inside the lock — collect structured errors so the
            # template can display them per-producer.
            producer_errors: list[dict] = []
            for item in cart:
                try:
                    product = product_by_id.get(int(item["product_id"]))
                    if not product:
                        raise Product.DoesNotExist()
                    if product.stock <= 0:
                        producer_errors.append({
                            "producer_name": product.producer.full_name,
                            "message": f"{item['name']} is out of stock.",
                        })
                    elif item["quantity"] > product.stock:
                        producer_errors.append({
                            "producer_name": product.producer.full_name,
                            "message": (
                                f"{item['name']}: only {product.stock} in stock "
                                f"(you requested {item['quantity']})."
                            ),
                        })
                except Product.DoesNotExist:
                    producer_errors.append({
                        "producer_name": "Unknown",
                        "message": f"Product '{item['name']}' is no longer available.",
                    })

            if producer_errors:
                return render(
                    request,
                    self.template_name,
                    self._build_context(
                        request, form, cart,
                        product_by_id=product_by_id,
                        producer_errors=producer_errors,
                    ),
                )

            checkout_order = form.save(commit=False)
            checkout_order.customer = request.user
            checkout_order.save()

            # Group items by producer to create one vendor Order per producer.
            grouped: dict[int, list[tuple[Product, int]]] = defaultdict(list)
            gross_total = Decimal("0.00")
            for item in cart:
                product = product_by_id.get(int(item["product_id"]))
                if not product:
                    continue
                qty = int(item["quantity"])
                grouped[product.producer_id].append((product, qty))
                gross_total += Decimal(str(product.price)) * qty

            base_order_id = f"CO-{checkout_order.id}"
            is_multi_vendor = len(grouped) > 1

            created_vendor_orders: list[str] = []
            for producer_id, lines in grouped.items():
                producer = lines[0][0].producer
                vendor_order_id = (
                    base_order_id if not is_multi_vendor else f"{base_order_id}-{producer_id}"
                )
                # Use the per-producer delivery date submitted from the checkout form.
                delivery_date = producer_delivery_dates.get(producer_id)

                # Calculate per-producer subtotal and 5% commission.
                producer_subtotal = sum(
                    Decimal(str(p.price)) * qty for p, qty in lines
                )
                producer_commission = (producer_subtotal * self._commission_rate).quantize(Decimal("0.01"))

                vendor_order = Order.objects.create(
                    order_id=vendor_order_id,
                    customer_name=checkout_order.full_name,
                    delivery_date=delivery_date,
                    status="Pending",
                    producer=producer,
                    expires_at=timezone.now() + timedelta(hours=48),
                    commission=producer_commission,
                )
                for product, qty in lines:
                    OrderItem.objects.create(
                        order=vendor_order,
                        product=product,
                        quantity=qty,
                        unit_price=product.price,
                    )
                created_vendor_orders.append(vendor_order.order_id)

            # Decrement stock and broadcast real-time updates.
            for item in cart:
                product = product_by_id.get(int(item["product_id"]))
                if not product:
                    continue
                product.stock = max(0, product.stock - int(item["quantity"]))
                if product.stock == 0:
                    product.status = "Out of Stock"
                product.save()
                _broadcast_stock_update(product)

            # Update today's commission report (automatic 5% network commission).
            report_date = date.today()
            commission_amount = (gross_total * self._commission_rate).quantize(Decimal("0.01"))
            report, _ = CommissionReport.objects.get_or_create(
                report_date=report_date,
                defaults={
                    "total_orders": 0,
                    "gross_amount": Decimal("0.00"),
                    "commission_amount": Decimal("0.00"),
                },
            )
            report.total_orders += 1
            report.gross_amount = (
                Decimal(str(report.gross_amount)) + gross_total
            ).quantize(Decimal("0.01"))
            report.commission_amount = (
                Decimal(str(report.commission_amount)) + commission_amount
            ).quantize(Decimal("0.01"))
            report.save()

            # Preserve cart snapshot for the confirmation page, then clear.
            request.session["last_order_cart"] = cart
            request.session["last_order_total"] = float(gross_total.quantize(Decimal("0.01")))
            request.session["last_order_base_id"] = base_order_id
            request.session["last_order_vendor_ids"] = created_vendor_orders
            request.session["cart"] = []
            _clear_reservations(_ensure_session_key(request))

            messages.success(request, "Order placed successfully!")
            return redirect(f"/orders/{checkout_order.id}/confirmation/")


class OrderConfirmationView(CustomerRequiredMixin, TemplateView):
    template_name = "customer/order_confirmation.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        order = get_object_or_404(CheckoutOrder, pk=self.kwargs["order_id"], customer=self.request.user)
        ctx["order"] = order

        # Base order ID used in vendor order IDs (e.g. "CO-7").
        base_order_id = f"CO-{order.id}"
        ctx["customer_order_id"] = base_order_id

        # Always load vendor orders directly from the DB so this page works
        # both immediately after checkout AND when revisited from order history.
        vendor_orders = list(
            Order.objects.filter(order_id__startswith=base_order_id)
            .select_related("producer")
            .prefetch_related("items__product")
        )
        grand_total = Decimal("0")
        for vo in vendor_orders:
            subtotal = Decimal("0")
            for oi in vo.items.all():
                oi.line_total = (Decimal(str(oi.unit_price)) * oi.quantity).quantize(Decimal("0.01"))
                subtotal += oi.line_total
            vo.subtotal = subtotal.quantize(Decimal("0.01"))
            grand_total += subtotal
        ctx["vendor_orders"] = vendor_orders
        ctx["vendor_order_ids"] = [vo.order_id for vo in vendor_orders]

        # Prefer the live-computed total; fall back to session snapshot if
        # no items were loaded (edge case: all products deleted after order).
        ctx["total"] = float(grand_total) if grand_total else self.request.session.get("last_order_total", 0)
        return ctx


# ── Producer views ────────────────────────────────────────────────────────────

class ProducerDashboardView(ProducerRequiredMixin, View):
    template_name = "producer/dashboard.html"

    def get(self, request):
        producer = request.user
        low_stock_qs = Product.objects.filter(
            producer=producer,
            stock__gt=0,
            stock__lte=F("low_stock_threshold"),
        ).order_by("stock")
        ctx = {
            "summary": {
                "orders_today": Order.objects.filter(
                    producer=producer,
                    delivery_date=date.today(),
                ).count(),
                "low_stock_count": low_stock_qs.count(),
            },
            "low_stock_products": low_stock_qs,
        }
        return render(request, self.template_name, ctx)


class ProducerProductsView(ProducerRequiredMixin, View):
    template_name = "producer/products.html"

    def _render(self, request, form=None):
        products = Product.objects.filter(producer=request.user).order_by("name")
        return render(request, self.template_name, {
            "products": products,
            "form": form or ProductForm(),
        })

    def get(self, request):
        return self._render(request)

    def post(self, request):
        form = ProductForm(request.POST)
        if not form.is_valid():
            return self._render(request, form=form)

        data = form.cleaned_data
        stock = data["stock"]
        status = data["status"] if stock > 0 else "Out of Stock"

        Product.objects.create(
            name=data["name"],
            category=data["category"],
            description=data.get("description", ""),
            price=data["price"],
            stock=stock,
            status=status,
            allergens=data.get("allergens", ""),
            is_organic=data.get("is_organic", False),
            producer=request.user,
        )
        messages.success(request, "Product created successfully.")
        return redirect("/producer/products/")


class ProducerProductEditView(ProducerRequiredMixin, View):
    template_name = "producer/product_edit.html"

    def _get_product(self, request, pk):
        return get_object_or_404(Product, pk=pk, producer=request.user)

    def get(self, request, pk):
        product = self._get_product(request, pk)
        return render(request, self.template_name, {"form": ProductForm(instance=product), "product": product})

    def post(self, request, pk):
        product = self._get_product(request, pk)
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            updated = form.save(commit=False)
            if updated.stock == 0:
                updated.status = "Out of Stock"
            elif updated.status == "Out of Stock" and updated.stock > 0:
                updated.status = "Available"
            # low_stock_threshold is optional in the form; keep the existing value if blank
            if form.cleaned_data.get("low_stock_threshold") is None:
                updated.low_stock_threshold = product.low_stock_threshold
            updated.save()
            _broadcast_stock_update(updated)
            messages.success(request, "Product updated.")
            return redirect("/producer/products/")
        return render(request, self.template_name, {"form": form, "product": product})


class ProducerOrdersView(ProducerRequiredMixin, TemplateView):
    template_name = "producer/orders.html"

    _next_status = {
        "pending": "Confirmed",
        "confirmed": "Ready",
        "ready": "Delivered",
    }

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        orders = Order.objects.filter(producer=self.request.user).order_by("delivery_date")
        ctx["orders"] = [
            {
                "order_id": o.order_id,
                "customer_name": o.customer_name,
                "delivery_date": o.delivery_date,
                "status": o.status,
                # None when already Delivered — no further transitions allowed
                "next_status": self._next_status.get(o.status.lower()),
            }
            for o in orders
        ]
        return ctx


class ProducerOrderDetailView(ProducerRequiredMixin, TemplateView):
    template_name = "producer/order_detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        order = get_object_or_404(Order, order_id=self.kwargs["order_id"], producer=self.request.user)
        items = order.items.select_related("product").order_by("id")
        ctx["order"] = order
        ctx["items"] = [
            {
                "name": item.product.name,
                "quantity": item.quantity,
                "unit_price": float(item.unit_price),
                "line_total": round(item.quantity * float(item.unit_price), 2),
            }
            for item in items
        ]
        ctx["order_total"] = round(sum(i["line_total"] for i in ctx["items"]), 2)
        return ctx


class ProducerOrderStatusUpdateView(ProducerRequiredMixin, View):
    _allowed_transitions = {
        "pending": "confirmed",
        "confirmed": "ready",
        "ready": "delivered",
    }

    def post(self, request, order_id):
        form = OrderStatusForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Invalid status.")
            return redirect("/producer/orders/")

        order = get_object_or_404(Order, order_id=order_id, producer=request.user)
        new_status = form.cleaned_data["status"].strip().lower()
        current = order.status.strip().lower()

        if self._allowed_transitions.get(current) != new_status:
            messages.error(request, f"Cannot move order from {current} to {new_status}.")
            return redirect("/producer/orders/")

        order.status = new_status.capitalize()
        order.save()

        # Push real-time notification to customer
        _broadcast_order_status(order)

        messages.success(request, "Order status updated.")
        return redirect("/producer/orders/")


class ProducerPaymentsView(ProducerRequiredMixin, View):
    template_name = "producer/payments.html"

    _commission_rate = Decimal("0.05")

    def _build_payment_data(self, producer):
        delivered_items = OrderItem.objects.filter(
            order__producer=producer,
            order__status="Delivered",
        ).select_related("order")
        delivered_gross = sum(float(i.unit_price) * i.quantity for i in delivered_items)

        pending_items = OrderItem.objects.filter(
            order__producer=producer,
        ).exclude(order__status="Delivered").select_related("order")
        pending_gross = sum(float(i.unit_price) * i.quantity for i in pending_items)

        commission = round(delivered_gross * float(self._commission_rate), 2)

        all_orders_qs = (
            Order.objects.filter(producer=producer)
            .prefetch_related("items")
            .order_by("-delivery_date")
        )
        orders = []
        for o in all_orders_qs:
            total = sum(float(i.unit_price) * i.quantity for i in o.items.all())
            orders.append({
                "order_id": o.order_id,
                "customer_name": o.customer_name,
                "delivery_date": o.delivery_date,
                "status": o.status,
                "gross": round(total, 2),
                "commission": round(total * float(self._commission_rate), 2),
                "net": round(total * (1 - float(self._commission_rate)), 2),
            })

        pending_orders = [o for o in orders if o["status"] == "Pending"]

        return {
            "summary": {
                "this_week": round(delivered_gross, 2),
                "pending": round(pending_gross, 2),
                "commission": commission,
                "net_earned": round(delivered_gross * (1 - float(self._commission_rate)), 2),
            },
            "orders": orders,
            "pending_orders": pending_orders,
        }

    def get(self, request):
        producer = request.user
        data = self._build_payment_data(producer)

        if request.GET.get("export") == "csv":
            response = HttpResponse(content_type="text/csv")
            response["Content-Disposition"] = 'attachment; filename="payment_report.csv"'
            writer = csv.writer(response)
            writer.writerow(["Order ID", "Customer", "Delivery Date", "Status", "Gross (£)", "Commission (£)", "Net (£)"])
            for o in data["orders"]:
                writer.writerow([
                    o["order_id"],
                    o["customer_name"],
                    o["delivery_date"] or "",
                    o["status"],
                    f"{o['gross']:.2f}",
                    f"{o['commission']:.2f}",
                    f"{o['net']:.2f}",
                ])
            writer.writerow([])
            s = data["summary"]
            writer.writerow(["", "", "", "TOTAL", f"{s['this_week']:.2f}", f"{s['commission']:.2f}", f"{s['net_earned']:.2f}"])
            return response

        return render(request, self.template_name, {
            "payments": data["summary"],
            "pending_orders": data["pending_orders"],
            "all_orders": data["orders"],
        })


# ── Admin views ───────────────────────────────────────────────────────────────

class AdminDashboardView(AdminRequiredMixin, TemplateView):
    template_name = "admin_panel/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = date.today()
        commission_today = CommissionReport.objects.filter(
            report_date=today,
        ).aggregate(total=Sum("commission_amount"))["total"] or 0
        ctx["summary"] = {
            "commission_today": round(float(commission_today), 2),
            "active_users": User.objects.filter(status="active").count(),
            "open_flags": QualityAssessment.objects.filter(
                model_confidence__lt=0.60,
            ).count(),
        }
        return ctx


class AdminReportsView(AdminRequiredMixin, View):
    template_name = "admin_panel/reports.html"
    _PAGE_SIZE = 10

    def get(self, request):
        form = ReportFilterForm(request.GET or None)
        qs = CommissionReport.objects.all()
        if form.is_valid():
            df = form.cleaned_data.get("date_from")
            dt = form.cleaned_data.get("date_to")
            if df:
                qs = qs.filter(report_date__gte=df)
            if dt:
                qs = qs.filter(report_date__lte=dt)

        # Optional CSV export for assessment evidence
        if request.GET.get("export") == "csv":
            response = HttpResponse(content_type="text/csv")
            response["Content-Disposition"] = 'attachment; filename="commission_reports.csv"'
            writer = csv.writer(response)
            writer.writerow(["date", "orders", "gross", "commission"])
            for r in qs:
                writer.writerow([str(r.report_date), r.total_orders, f"{float(r.gross_amount):.2f}", f"{float(r.commission_amount):.2f}"])
            return response

        rows = [
            {
                "date": str(r.report_date),
                "orders": r.total_orders,
                "gross": float(r.gross_amount),
                "commission": float(r.commission_amount),
            }
            for r in qs
        ]

        paginator = Paginator(rows, self._PAGE_SIZE)
        page_obj = paginator.get_page(request.GET.get("page") or 1)

        # Per-producer breakdown from Order/OrderItem data
        item_qs = OrderItem.objects.select_related("order__producer")
        if form.is_valid():
            df = form.cleaned_data.get("date_from")
            dt = form.cleaned_data.get("date_to")
            if df:
                item_qs = item_qs.filter(order__created_at__date__gte=df)
            if dt:
                item_qs = item_qs.filter(order__created_at__date__lte=dt)
        producer_breakdown = (
            item_qs
            .values("order__producer__full_name", "order__producer__email")
            .annotate(
                order_count=Count("order_id", distinct=True),
                gross=Sum(
                    ExpressionWrapper(
                        F("unit_price") * F("quantity"),
                        output_field=DecimalField(max_digits=12, decimal_places=2),
                    )
                ),
            )
            .order_by("-gross")
        )
        producer_rows = [
            {
                "name": r["order__producer__full_name"] or r["order__producer__email"],
                "email": r["order__producer__email"],
                "orders": r["order_count"],
                "gross": round(float(r["gross"] or 0), 2),
                "commission": round(float(r["gross"] or 0) * 0.05, 2),
                "net_payout": round(float(r["gross"] or 0) * 0.95, 2),
            }
            for r in producer_breakdown
        ]

        return render(request, self.template_name, {
            "form": form,
            "rows": page_obj.object_list,
            "page_obj": page_obj,
            "total_orders": sum(r["orders"] for r in rows),
            "total_gross": round(sum(r["gross"] for r in rows), 2),
            "total_commission": round(sum(r["commission"] for r in rows), 2),
            "producer_rows": producer_rows,
        })


class AdminUsersView(AdminRequiredMixin, ListView):
    template_name = "admin_panel/users.html"
    context_object_name = "users"

    def get_queryset(self):
        return User.objects.all().order_by("role", "email")


class AdminDatabaseView(AdminRequiredMixin, TemplateView):
    template_name = "admin_panel/database.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["db_users"] = User.objects.values(
            "id", "email", "role", "full_name", "status",
        ).order_by("id")
        ctx["db_products"] = [
            {**p, "price": float(p["price"])}
            for p in Product.objects.values(
                "id", "name", "category", "price", "stock", "status", "producer_id",
            ).order_by("id")
        ]
        ctx["db_orders"] = [
            {**o, "delivery_date": str(o["delivery_date"]) if o["delivery_date"] else None}
            for o in Order.objects.values(
                "id", "order_id", "customer_name", "delivery_date", "status", "producer_id",
            ).order_by("id")
        ]
        return ctx


# ── AI views ──────────────────────────────────────────────────────────────────

class ProducerQualityCheckView(ProducerRequiredMixin, View):
    template_name = "producer/quality_check.html"

    def _render(self, request, result=None):
        return render(request, self.template_name, {
            "result": result,
            "products": Product.objects.filter(producer=request.user),
            "assessments": get_producer_assessments(request.user),
        })

    def get(self, request):
        return self._render(request)

    def post(self, request):
        action = (request.POST.get("action") or "").strip()
        if action == "deduct_rotten_stock":
            assessment_id = request.POST.get("assessment_id")
            qty_raw = request.POST.get("quantity")

            if not assessment_id or not str(assessment_id).isdigit():
                messages.error(request, "Missing assessment reference.")
                return redirect("/producer/quality-check/")

            assessment = get_object_or_404(
                QualityAssessment.objects.select_related("product"),
                id=int(assessment_id),
                product__producer=request.user,
            )

            if assessment.is_healthy:
                messages.error(request, "This assessment was not flagged as rotten — stock deduction cancelled.")
                return redirect("/producer/quality-check/")

            try:
                qty = int(qty_raw)
            except (TypeError, ValueError):
                qty = 0

            if qty < 1:
                messages.error(request, "Please enter a valid quantity (1 or more).")
                return redirect("/producer/quality-check/")

            product = assessment.product
            if qty > product.stock:
                messages.error(request, f"You only have {product.stock} units in stock.")
                return redirect("/producer/quality-check/")

            product.stock = max(0, product.stock - qty)
            if product.stock == 0:
                product.status = "Out of Stock"
            product.save()

            assessment.quantity_lost = int(assessment.quantity_lost or 0) + qty
            deduction_note = f"Stock deduction: {qty} unit(s) removed on {date.today().isoformat()} (AI rotten check)."
            if assessment.notes:
                assessment.notes = assessment.notes.rstrip() + "\n" + deduction_note
            else:
                assessment.notes = deduction_note
            assessment.save(update_fields=["quantity_lost", "notes"])

            messages.success(request, f"Deducted {qty} unit(s) from {product.name}.")
            return redirect("/producer/quality-check/")

        product_id = request.POST.get("product_id")
        image_file = request.FILES.get("image")
        if not product_id or not image_file:
            messages.error(request, "Please select a product and upload an image.")
            return self._render(request)
        try:
            result = assess_product_image(image_file, int(product_id), request.user)
            try:
                product = Product.objects.get(id=int(product_id), producer=request.user)
                result["product_id"] = product.id
                result["current_stock"] = product.stock
            except Product.DoesNotExist:
                pass
            messages.success(
                request,
                f"Quality check complete: Grade {result['grade']} "
                f"({result['model_confidence']:.0%} confidence)",
            )
            return self._render(request, result=result)
        except Product.DoesNotExist:
            messages.error(request, "Product not found or does not belong to you.")
        except Exception as exc:
            messages.error(request, f"Assessment failed: {exc}")
        return self._render(request)


class AdminAIMonitoringView(AdminRequiredMixin, TemplateView):
    template_name = "admin_panel/ai_monitoring.html"

    def get_context_data(self, **kwargs):
        import json, pathlib
        ctx = super().get_context_data(**kwargs)
        ctx["stats"] = get_ai_monitoring_stats()
        ctx["recent_assessments"] = (
            QualityAssessment.objects
            .select_related("product", "assessed_by")
            .order_by("-assessed_at")[:20]
        )
        # Load model metrics JSON if it exists
        metrics_path = pathlib.Path(__file__).resolve().parent.parent / "ml" / "saved_models" / "model_metrics.json"
        if metrics_path.exists():
            with open(metrics_path) as f:
                ctx["model_metrics"] = json.load(f)
        # Check if confusion matrix image exists
        cm_path = pathlib.Path(__file__).resolve().parent.parent / "ml" / "saved_models" / "confusion_matrix.png"
        ctx["has_confusion_matrix"] = cm_path.exists()
        return ctx


class AdminAIAssessmentDetailView(AdminRequiredMixin, View):
    """Shows XAI heatmap + explanation for a single quality assessment."""
    template_name = "admin_panel/ai_assessment_detail.html"

    def get(self, request, pk):
        assessment = get_object_or_404(
            QualityAssessment.objects.select_related("product", "assessed_by"),
            pk=pk,
        )
        xai_heatmap = None
        xai_explanation = None
        # Re-run inference on stored image to get heatmap
        try:
            from ml.inference import classify_image
            image_path = assessment.image.path
            with open(image_path, "rb") as f:
                image_bytes = f.read()
            result = classify_image(image_bytes, explain=True)
            xai_heatmap = result.get("xai_heatmap")
            xai_explanation = result.get("xai_explanation")
        except Exception:
            pass
        return render(request, self.template_name, {
            "assessment": assessment,
            "xai_heatmap": xai_heatmap,
            "xai_explanation": xai_explanation,
        })


class AdminModelUploadView(AdminRequiredMixin, View):
    """Allow AI engineers (admin role) to replace the active ML model."""

    _model_path = pathlib.Path(__file__).resolve().parent.parent / "ml" / "saved_models" / "quality_classifier.pt"
    _backup_path = pathlib.Path(__file__).resolve().parent.parent / "ml" / "saved_models" / "quality_classifier_prev.pt"

    def post(self, request):
        uploaded = request.FILES.get("model_file")
        if not uploaded:
            messages.error(request, "No file uploaded.")
            return redirect("admin_ai_monitoring")
        if not uploaded.name.endswith(".pt"):
            messages.error(request, "Only .pt (PyTorch) model files are accepted.")
            return redirect("admin_ai_monitoring")

        model_bytes = uploaded.read()
        try:
            import io as _io
            import torch
            state = torch.load(_io.BytesIO(model_bytes), map_location="cpu", weights_only=True)
            if not isinstance(state, dict):
                raise ValueError("File does not contain a state_dict.")
        except Exception as exc:
            messages.error(request, f"Invalid model file: {exc}")
            return redirect("admin_ai_monitoring")

        self._model_path.parent.mkdir(parents=True, exist_ok=True)
        if self._model_path.exists():
            import shutil
            shutil.copy2(self._model_path, self._backup_path)

        with open(self._model_path, "wb") as f:
            f.write(model_bytes)

        # Clear the in-process model cache so next inference loads the new file
        import ml.inference as _inf
        _inf._model = None

        messages.success(request, f"Model '{uploaded.name}' uploaded successfully. Cache cleared.")
        return redirect("admin_ai_monitoring")


class AdminInteractionExportView(AdminRequiredMixin, View):
    """Export all QualityAssessment interaction records as CSV for model refinement."""

    def get(self, request):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="ai_interactions.csv"'
        writer = csv.writer(response)
        writer.writerow([
            "id", "product_name", "producer_email", "grade",
            "color_score", "size_score", "ripeness_score",
            "model_confidence", "model_version", "is_healthy",
            "notes", "quantity_lost", "assessed_at", "image_path",
        ])
        qs = (
            QualityAssessment.objects
            .select_related("product", "assessed_by")
            .order_by("-assessed_at")
        )
        for a in qs:
            writer.writerow([
                a.id,
                a.product.name,
                a.assessed_by.email if a.assessed_by else "",
                a.grade,
                round(a.color_score, 2),
                round(a.size_score, 2),
                round(a.ripeness_score, 2),
                round(a.model_confidence, 4),
                a.model_version,
                a.is_healthy,
                a.notes.replace("\n", " "),
                a.quantity_lost,
                a.assessed_at.isoformat(),
                a.image.name if a.image else "",
            ])
        return response


class AdminConfusionMatrixView(AdminRequiredMixin, View):
    """Serves the confusion_matrix.png generated by ml/evaluate.py."""

    def get(self, request):
        import pathlib
        cm_path = pathlib.Path(__file__).resolve().parent.parent / "ml" / "saved_models" / "confusion_matrix.png"
        if not cm_path.exists():
            return HttpResponse("Confusion matrix not found. Run ml/evaluate.py to generate it.", status=404)
        with open(cm_path, "rb") as f:
            return HttpResponse(f.read(), content_type="image/png")


class ReorderView(CustomerRequiredMixin, View):
    """Re-adds all available items from a past order into the current cart."""

    def post(self, request, order_id):
        order = get_object_or_404(CheckoutOrder, pk=order_id, customer=request.user)
        base_order_id = f"CO-{order.id}"
        session_key = _ensure_session_key(request)
        vendor_orders = (
            Order.objects.filter(order_id__startswith=base_order_id)
            .prefetch_related("items__product__producer")
        )
        cart = request.session.get("cart", [])
        added = 0
        updated = 0
        skipped = 0
        for vo in vendor_orders:
            for oi in vo.items.all():
                product = oi.product
                if product.status not in ("Available", "In Season") or product.stock < 1:
                    skipped += 1
                    continue
                qty = min(oi.quantity, product.stock)
                for item in cart:
                    if item["product_id"] == product.id:
                        item["quantity"] = min(item["quantity"] + qty, product.stock)
                        _upsert_reservation(session_key, product.id, item["quantity"])
                        updated += 1
                        break
                else:
                    cart.append({
                        "product_id": product.id,
                        "name": product.name,
                        "price": float(product.price),
                        "quantity": qty,
                        "producer_id": product.producer_id,
                        "producer_name": product.producer.full_name,
                    })
                    _upsert_reservation(session_key, product.id, qty)
                    added += 1
        request.session["cart"] = cart
        if added > 0 or updated > 0:
            msg = []
            if added:
                msg.append(f"{added} new item(s) added")
            if updated:
                msg.append(f"{updated} item(s) updated")
            messages.success(request, f"{', '.join(msg)} in your cart from {base_order_id}.")
        elif skipped > 0:
            messages.warning(request, "No items could be re-added — all are currently out of stock.")
        else:
            messages.info(request, "That order had no items to re-add.")
        return redirect("/cart/")


class OrderReceiptView(CustomerRequiredMixin, View):
    """Renders a printable HTML receipt for a past order."""

    def get(self, request, order_id):
        order = get_object_or_404(CheckoutOrder, pk=order_id, customer=request.user)
        base_order_id = f"CO-{order.id}"
        vendor_orders = list(
            Order.objects.filter(order_id__startswith=base_order_id)
            .select_related("producer")
            .prefetch_related("items__product")
        )
        grand_total = Decimal("0")
        for vo in vendor_orders:
            subtotal = Decimal("0")
            for oi in vo.items.all():
                oi.line_total = (Decimal(str(oi.unit_price)) * oi.quantity).quantize(Decimal("0.01"))
                subtotal += oi.line_total
            vo.subtotal = subtotal.quantize(Decimal("0.01"))
            grand_total += subtotal
        return render(request, "customer/order_receipt.html", {
            "order": order,
            "base_order_id": base_order_id,
            "vendor_orders": vendor_orders,
            "grand_total": grand_total,
        })


# ── Error views ───────────────────────────────────────────────────────────────

def view_401(request):
    return render(request, "errors/401.html", status=401)


def view_403(request):
    return render(request, "errors/403.html", status=403)


def view_404(request, exception=None):
    return render(request, "errors/404.html", status=404)
