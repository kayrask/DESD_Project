"""
Django template-based views (MVT pattern).

Models  → api/models.py
Views   → here (class-based views using Django ORM directly)
Templates → api/templates/
"""

from datetime import date, datetime as _dt, timedelta
from decimal import Decimal
import csv
import logging
import pathlib
import random
import secrets
from collections import defaultdict

logger = logging.getLogger(__name__)

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from api.email_utils import send_email
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from django.views.generic import ListView, TemplateView

from api.food_miles import calculate_food_miles as _calc_miles
from api.forms import (
    CheckoutForm,
    FarmStoryForm,
    LoginForm,
    OrderStatusForm,
    ProductForm,
    RecipeForm,
    ReportFilterForm,
    RegisterForm,
    ReviewForm,
)
from api.models import (
    AdminOTP,
    CartReservation,
    CheckoutOrder,
    CommissionReport,
    EmailVerificationToken,
    FarmStory,
    Order,
    OrderItem,
    PasswordResetToken,
    PaymentSettlement,
    Product,
    QualityAssessment,
    QualityOverride,
    Recipe,
    RecurringOrder,
    RecurringOrderNotification,
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
    try:
        async_to_sync(layer.group_send)(f"order_{order.order_id}", payload)
        parts = order.order_id.split("-")  # CO-1 or CO-1-42
        checkout_id = int(parts[1])
        from api.models import CheckoutOrder
        co = CheckoutOrder.objects.filter(id=checkout_id).select_related("customer").first()
        if co and co.customer_id:
            async_to_sync(layer.group_send)(f"user_{co.customer_id}", payload)
    except (IndexError, ValueError):
        pass
    except Exception:
        logger.exception("broadcast_order_status failed for %s", order.order_id)


def _broadcast_new_order_to_producer(order):
    """Notify producer WebSocket connections about a new incoming order."""
    from asgiref.sync import async_to_sync
    layer = _get_channel_layer()
    if layer is None:
        return
    group = f"user_{order.producer_id}"
    try:
        async_to_sync(layer.group_send)(group, {
            "type": "new_order",
            "order_id": order.order_id,
            "customer_name": order.customer_name or "",
        })
    except Exception:
        logger.exception("_broadcast_new_order_to_producer failed for %s", order.order_id)


def _broadcast_stock_update(product):
    """Notify all product-list pages about a stock change."""
    from asgiref.sync import async_to_sync
    layer = _get_channel_layer()
    if layer is None:
        return
    try:
        async_to_sync(layer.group_send)(
            "stock_updates",
            {"type": "stock.update", "product_id": product.id, "stock": product.stock, "status": product.status},
        )
    except Exception:
        logger.exception("broadcast_stock_update failed for product %s", product.id)


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


# ── Constants ─────────────────────────────────────────────────────────────────

COMMON_ALLERGENS = ["Milk", "Eggs", "Gluten", "Nuts", "Soy", "Sesame", "Shellfish", "Fish"]


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
        exclude_allergens = [
            a for a in self.request.GET.getlist("exclude_allergens")
            if a in COMMON_ALLERGENS
        ]
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
        for allergen in exclude_allergens:
            qs = qs.exclude(allergens__icontains=allergen)
        min_price = self.request.GET.get("min_price", "").strip()
        max_price = self.request.GET.get("max_price", "").strip()
        if min_price:
            try:
                qs = qs.filter(price__gte=Decimal(min_price))
            except Exception:
                pass
        if max_price:
            try:
                qs = qs.filter(price__lte=Decimal(max_price))
            except Exception:
                pass
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
        ctx["allergen_options"] = COMMON_ALLERGENS
        ctx["selected_allergens"] = [
            a for a in self.request.GET.getlist("exclude_allergens")
            if a in COMMON_ALLERGENS
        ]
        ctx["min_price"] = self.request.GET.get("min_price", "")
        ctx["max_price"] = self.request.GET.get("max_price", "")

        # ── Producer search results (shown when query matches a producer name / org) ──
        q = self.request.GET.get("q", "").strip()
        matching_producers = []
        if q:
            producer_qs = User.objects.filter(
                role="producer",
                status="active",
            ).filter(
                Q(full_name__icontains=q) | Q(organization_name__icontains=q)
            )[:6]
            for p in producer_qs:
                product_count = Product.objects.filter(
                    producer=p, status__in=("Available", "In Season")
                ).count()
                reviews = Review.objects.filter(product__producer=p)
                review_count = reviews.count()
                avg = round(sum(r.rating for r in reviews) / review_count, 1) if review_count else None
                matching_producers.append({
                    "producer": p,
                    "product_count": product_count,
                    "review_count": review_count,
                    "avg_rating": avg,
                })
        ctx["matching_producers"] = matching_producers

        ctx["recommendations"] = []
        ctx["rec_model_version"] = ""

        if self.request.user.is_authenticated and self.request.user.role == "customer":
            try:
                recs = recommend_products(limit=4, customer_email=self.request.user.email)
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
                pass
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
                if user.status == "suspended":
                    form.add_error(
                        None,
                        "Your account is pending admin approval. "
                        "You will be notified by email once it is activated.",
                    )
                    return render(request, self.template_name, {"form": form})
                db_user = User.objects.filter(pk=user.pk).first()
                if db_user and not db_user.email_verified:
                    form.add_error(
                        None,
                        "Please verify your email first. Check your inbox for a verification link.",
                    )
                    return render(request, self.template_name, {"form": form})
                next_url = request.GET.get("next", "/")
                if not next_url.startswith("/"):
                    next_url = "/"
                if user.role == "admin":
                    code = f"{random.randint(0, 999999):06d}"
                    AdminOTP.objects.create(
                        user=user,
                        code=code,
                        expires_at=timezone.now() + timedelta(minutes=5),
                    )
                    send_email(
                        user.email,
                        "Your DESD Admin Login Code",
                        f"Your one-time login code is: {code}\n\nThis code expires in 5 minutes.\nDo not share it with anyone.",
                    )
                    request.session["otp_user_id"] = user.pk
                    return redirect(f"/login/otp/?next={next_url}")
                login(request, user)
                messages.success(request, f"Welcome back, {user.full_name}!")
                return redirect(next_url)
            form.add_error(None, "Invalid email or password.")
        return render(request, self.template_name, {"form": form})


class LogoutView(View):
    def post(self, request):
        logout(request)
        messages.info(request, "You have been logged out.")
        return redirect("/login/")


class AdminOTPVerifyView(View):
    template_name = "otp_verify.html"

    def get(self, request):
        if "otp_user_id" not in request.session:
            return redirect("/login/")
        return render(request, self.template_name, {})

    def post(self, request):
        user_id = request.session.get("otp_user_id")
        if not user_id:
            return redirect("/login/")
        code = request.POST.get("code", "").strip()
        try:
            otp = AdminOTP.objects.get(
                user_id=user_id,
                code=code,
                is_used=False,
                expires_at__gt=timezone.now(),
            )
        except AdminOTP.DoesNotExist:
            messages.error(request, "Invalid or expired code. Please try again.")
            return render(request, self.template_name, {})
        otp.is_used = True
        otp.save()
        del request.session["otp_user_id"]
        user = User.objects.get(pk=user_id)
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(request, f"Welcome back, {user.full_name}!")
        next_url = request.GET.get("next", "/")
        if not next_url.startswith("/"):
            next_url = "/"
        return redirect(next_url)


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
            role = form.cleaned_data["role"]
            # Producers should not set account_type/organization_name
            if role == "producer":
                account_type = "individual"
                organization_name = ""
            else:
                account_type = form.cleaned_data.get("account_type") or "individual"
                organization_name = form.cleaned_data.get("organization_name", "")
            needs_approval = account_type in ("community_group", "restaurant")
            new_user = User.objects.create_user(
                email=email,
                password=form.cleaned_data["password"],
                full_name=form.cleaned_data["full_name"],
                role=role,
                account_type=account_type,
                organization_name=organization_name,
                status="suspended" if needs_approval else "active",
            )
            # Mark email as unverified and create a verification token
            new_user.email_verified = False
            new_user.save()
            verification_token = secrets.token_urlsafe(32)
            EmailVerificationToken.objects.create(user=new_user, token=verification_token)
            verify_link = f"{request.scheme}://{request.get_host()}/verify-email/{verification_token}/"
            try:
                send_email(
                    new_user.email,
                    "Verify your DESD Marketplace email",
                    (
                        f"Hi {new_user.full_name or new_user.email},\n\n"
                        "Please verify your email address by clicking the link below:\n\n"
                        f"{verify_link}\n\n"
                        "This link does not expire.\n\n"
                        "Thanks,\nThe DESD Marketplace Team"
                    ),
                )
            except Exception:
                logger.exception("Failed to send verification email to %s", new_user.email)
            if needs_approval:
                messages.info(
                    request,
                    "Your account has been submitted for admin approval. "
                    "Please also check your email to verify your address.",
                )
            else:
                messages.info(
                    request,
                    "Account created! Please check your email to verify your address before logging in.",
                )
            # Redirect to login so users can proceed to sign in after
            # creating their account (email verification is requested
            # but does not block reaching the login page in tests).
            return redirect("/login/")
        return render(request, self.template_name, {"form": form})


class EmailVerifyPendingView(View):
    """Shown immediately after registration — tells the user to check their email."""
    template_name = "email_verify_pending.html"

    def get(self, request):
        return render(request, self.template_name, {})


class VerifyEmailView(View):
    """Processes the email verification link."""

    def get(self, request, token):
        try:
            ev_token = EmailVerificationToken.objects.select_related("user").get(token=token)
        except EmailVerificationToken.DoesNotExist:
            messages.error(request, "Verification link is invalid or has already been used.")
            return redirect("/login/")
        user = ev_token.user
        user.email_verified = True
        user.save()
        ev_token.delete()
        messages.success(request, "Email verified! You can now log in.")
        return redirect("/login/")


class ForgotPasswordView(View):
    template_name = "forgot_password.html"

    def get(self, request):
        return render(request, self.template_name, {})

    def post(self, request):
        email = request.POST.get("email", "").strip().lower()
        # Always show the same message to avoid revealing whether an account exists
        try:
            user = User.objects.get(email__iexact=email)
            token = secrets.token_urlsafe(32)
            PasswordResetToken.objects.create(user=user, token=token)
            reset_link = f"{request.scheme}://{request.get_host()}/reset-password/{token}/"
            send_email(
                user.email,
                "Reset your DESD Marketplace password",
                (
                    f"Hi {user.full_name or user.email},\n\n"
                    "We received a request to reset your password.\n\n"
                    "Click the link below to choose a new password:\n\n"
                    f"{reset_link}\n\n"
                    "This link expires in 1 hour. If you did not request a reset, ignore this email.\n\n"
                    "Thanks,\nThe DESD Marketplace Team"
                ),
            )
        except User.DoesNotExist:
            pass  # Do not reveal whether the email exists
        except Exception:
            logger.exception("Failed to send password reset email to %s", email)
        messages.success(
            request,
            "If that email is registered, you will receive a password reset link shortly.",
        )
        return redirect("/forgot-password/")


class PasswordResetConfirmView(View):
    template_name = "password_reset_confirm.html"

    def _get_valid_token(self, token_str):
        """Return the PasswordResetToken if valid and unexpired, else None."""
        try:
            token = PasswordResetToken.objects.select_related("user").get(
                token=token_str, used=False
            )
        except PasswordResetToken.DoesNotExist:
            return None
        if token.created_at < timezone.now() - timedelta(hours=1):
            return None
        return token

    def get(self, request, token):
        token_obj = self._get_valid_token(token)
        if token_obj is None:
            messages.error(request, "This password reset link is invalid or has expired.")
            return render(request, self.template_name, {"token": token, "invalid": True})
        return render(request, self.template_name, {"token": token, "invalid": False})

    def post(self, request, token):
        token_obj = self._get_valid_token(token)
        if token_obj is None:
            messages.error(request, "This password reset link is invalid or has expired.")
            return render(request, self.template_name, {"token": token, "invalid": True})
        new_password = request.POST.get("new_password", "")
        confirm_password = request.POST.get("confirm_password", "")
        if len(new_password) < 8:
            messages.error(request, "Password must be at least 8 characters.")
            return render(request, self.template_name, {"token": token, "invalid": False})
        if new_password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, self.template_name, {"token": token, "invalid": False})
        user = token_obj.user
        user.set_password(new_password)
        user.save()
        token_obj.used = True
        token_obj.save()
        messages.success(request, "Password reset successfully. You can now log in.")
        return redirect("/login/")


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
        try:
            from app.services.reorder_service import predict_reorder_items
            ctx["reorder_suggestions"] = predict_reorder_items(getattr(user, "full_name", ""))
        except Exception:
            logger.exception("predict_reorder_items failed for %s", getattr(user, "email", "?"))
            ctx["reorder_suggestions"] = []
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
        producer_postcode = product.producer.postal_code or "BS1 4DJ"
        customer_postcode = request.user.postal_code if request.user.is_authenticated else "BS1 5JG"
        food_miles = _calc_miles(customer_postcode, producer_postcode)
        return {
            "product": product,
            "reviews": reviews,
            "avg_rating": avg_rating,
            "review_form": form or ReviewForm(),
            "existing_review": existing_review,
            "star_range": range(1, 6),
            "food_miles": food_miles,
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


class ProducerProfileView(View):
    """Public storefront for a producer — shows all their active products and stats."""

    template_name = "producer_profile.html"

    def get(self, request, pk):
        producer = get_object_or_404(User, pk=pk, role="producer", status="active")
        base_qs = Product.objects.filter(producer=producer, status__in=("Available", "In Season"))

        # All categories for the pills (unfiltered)
        categories = sorted({p.category for p in base_qs if p.category})
        total_products = base_qs.count()

        # Apply optional category filter within this producer's page
        selected_category = request.GET.get("category", "").strip()
        products = base_qs.filter(category=selected_category) if selected_category else base_qs
        products = products.order_by("name")

        all_reviews = Review.objects.filter(product__producer=producer)
        total_reviews = all_reviews.count()
        avg_rating = None
        if total_reviews > 0:
            avg_rating = round(sum(r.rating for r in all_reviews) / total_reviews, 1)

        return render(request, self.template_name, {
            "producer": producer,
            "products": products,
            "total_products": total_products,
            "categories": categories,
            "selected_category": selected_category,
            "total_reviews": total_reviews,
            "avg_rating": avg_rating,
            "star_range": range(1, 6),
        })


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
        customer_pc = self.request.user.postal_code if self.request.user.is_authenticated else "BS1 5JG"
        product_ids = [item["product_id"] for item in cart]
        products_map = {p.id: p for p in Product.objects.filter(id__in=product_ids).select_related("producer")}
        total_miles = sum(
            _calc_miles(customer_pc, products_map[item["product_id"]].producer.postal_code or "BS1 4DJ")
            for item in cart if item["product_id"] in products_map
        )
        ctx["total_food_miles"] = round(total_miles, 1)
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
                # Notify the producer via WebSocket that a new order has arrived
                try:
                    _broadcast_new_order_to_producer(vendor_order)
                except Exception:
                    logger.exception("Failed to broadcast new order to producer for %s", vendor_order.order_id)

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

            # Send order confirmation email to customer
            try:
                customer = request.user
                item_lines = "\n".join(
                    f"  - {i['name']} x{i['quantity']} @ £{float(i['price']):.2f}"
                    for i in cart
                )
                send_email(
                    customer.email,
                    f"Order Confirmation – {base_order_id}",
                    (
                        f"Hi {customer.full_name or customer.email},\n\n"
                        f"Thank you for your order! Here is a summary:\n\n"
                        f"Order ID: {base_order_id}\n"
                        f"Total: £{float(gross_total.quantize(Decimal('0.01'))):.2f}\n\n"
                        f"Items:\n{item_lines}\n\n"
                        "You can track your order status from your dashboard.\n\n"
                        "Thanks,\nThe DESD Marketplace Team"
                    ),
                )
            except Exception:
                logger.exception("Failed to send checkout confirmation email for order %s", base_order_id)

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
        import json as _json

        producer = request.user
        low_stock_qs = Product.objects.filter(
            producer=producer,
            stock__gt=0,
            stock__lte=F("low_stock_threshold"),
        ).order_by("stock")

        try:
            from app.services.forecast_service import get_demand_forecast_dashboard
            forecast = get_demand_forecast_dashboard(producer)
        except Exception:
            logger.exception("get_demand_forecast_dashboard failed for producer %s", producer.pk)
            forecast = {"products": [], "labels": [], "top_product": None, "high_demand_alert": None}

        try:
            from app.services.price_service import get_quality_trend
            quality_trend = get_quality_trend(producer, weeks=8)
        except Exception:
            quality_trend = []

        ctx = {
            "summary": {
                "orders_today": Order.objects.filter(
                    producer=producer,
                    delivery_date=date.today(),
                ).count(),
                "low_stock_count": low_stock_qs.count(),
            },
            "low_stock_products": low_stock_qs,
            "forecast": forecast,
            "forecast_json": _json.dumps(forecast),
            "quality_trend": quality_trend,
            "quality_trend_json": _json.dumps(quality_trend),
        }
        return render(request, self.template_name, ctx)


class ProducerProductsView(ProducerRequiredMixin, View):
    template_name = "producer/products.html"

    def _render(self, request, form=None):
        products = list(Product.objects.filter(producer=request.user).order_by("name"))
        try:
            from app.services.waste_service import get_waste_risks
            risks = get_waste_risks(products)
            for p in products:
                setattr(p, "waste_risk", risks.get(p.id))
        except Exception:
            for p in products:
                setattr(p, "waste_risk", None)
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
        status = "Available" if stock > 0 else "Out of Stock"

        Product.objects.create(
            name=data["name"],
            category=data["category"],
            description=data.get("description", ""),
            price=data["price"],
            stock=stock,
            status=status,
            allergens=data.get("allergens", ""),
            is_organic=data.get("is_organic", False),
            discount_percentage=data.get("discount_percentage", 0),
            ai_discount_percentage=0,
            ai_discount_active=False,
            producer=request.user,
        )
        messages.success(request, "Product saved successfully.")
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
            else:
                updated.status = "Available"
            # low_stock_threshold is optional in the form; keep the existing value if blank
            if form.cleaned_data.get("low_stock_threshold") is None:
                updated.low_stock_threshold = product.low_stock_threshold
            updated.save()
            _broadcast_stock_update(updated)
            messages.success(request, "Product updated successfully.")
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

        # Email the customer about the status change
        try:
            parts = order.order_id.split("-")
            checkout_id = int(parts[1])
            co = CheckoutOrder.objects.filter(id=checkout_id).select_related("customer").first()
            if co and co.customer and co.customer.email:
                customer = co.customer
                customer_name = customer.full_name or customer.email
                send_email(
                    customer.email,
                    f"Your order {order.order_id} is now {order.status}",
                    (
                        f"Hi {customer_name},\n\n"
                        f"Your order {order.order_id} from {order.producer.full_name} "
                        f"has been updated to: {order.status}.\n\n"
                        "Log in to your DESD account to view the full details.\n\n"
                        "Thanks,\nThe DESD Marketplace Team"
                    ),
                )
        except Exception:
            logger.exception("Failed to send order status email for %s", order.order_id)

        # Push real-time notification to customer
        _broadcast_order_status(order)

        messages.success(request, "Order status updated.")
        return redirect("/producer/orders/")


class ProducerPaymentsView(ProducerRequiredMixin, View):
    template_name = "producer/payments.html"

    _commission_rate = Decimal("0.05")

    def _build_payment_data(self, producer):
        # All-time delivered gross for the summary cards
        delivered_items = OrderItem.objects.filter(
            order__producer=producer,
            order__status="Delivered",
        ).select_related("order")
        delivered_gross = sum(float(i.unit_price) * i.quantity for i in delivered_items)

        pending_items = OrderItem.objects.filter(
            order__producer=producer,
        ).exclude(order__status__in=["Delivered", "Cancelled"]).select_related("order")
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

        # Weekly settlements history
        settlements = list(
            PaymentSettlement.objects.filter(producer=producer)
            .values(
                "reference", "week_start", "week_end",
                "gross_amount", "commission_amount", "net_amount",
                "order_count", "status", "created_at",
            )
            .order_by("-week_start")
        )

        # Tax year running total (calendar year Jan–Dec)
        current_year = date.today().year
        tax_year_net = round(
            sum(float(s["net_amount"]) for s in settlements if s["week_start"].year == current_year),
            2,
        )
        tax_year_gross = round(
            sum(float(s["gross_amount"]) for s in settlements if s["week_start"].year == current_year),
            2,
        )

        return {
            "summary": {
                "this_week": round(delivered_gross, 2),
                "pending": round(pending_gross, 2),
                "commission": commission,
                "net_earned": round(delivered_gross * (1 - float(self._commission_rate)), 2),
            },
            "orders": orders,
            "pending_orders": pending_orders,
            "settlements": settlements,
            "tax_year": current_year,
            "tax_year_net": tax_year_net,
            "tax_year_gross": tax_year_gross,
        }

    def _settlement_csv(self, producer, settlement_ref):
        """Return a CSV HttpResponse for a single settlement's order breakdown."""
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{settlement_ref}.csv"'
        writer = csv.writer(response)

        try:
            settlement = PaymentSettlement.objects.get(reference=settlement_ref, producer=producer)
        except PaymentSettlement.DoesNotExist:
            writer.writerow(["Settlement not found"])
            return response

        writer.writerow([f"Payment Settlement Report — {settlement.reference}"])
        writer.writerow([f"Week: {settlement.week_start}  to  {settlement.week_end}"])
        writer.writerow([f"Status: {settlement.status}"])
        writer.writerow([])
        writer.writerow(["Order ID", "Customer", "Delivery Date", "Product", "Qty", "Unit Price (£)", "Line Total (£)", "Commission (£)", "Net (£)"])

        week_orders = Order.objects.filter(
            producer=producer,
            status="Delivered",
            delivery_date__gte=settlement.week_start,
            delivery_date__lte=settlement.week_end,
        ).prefetch_related("items__product")

        for o in week_orders:
            items = list(o.items.all())
            order_gross = sum(float(i.unit_price) * i.quantity for i in items)
            order_comm = round(order_gross * float(self._commission_rate), 2)
            order_net = round(order_gross * (1 - float(self._commission_rate)), 2)
            for idx, item in enumerate(items):
                line_total = round(float(item.unit_price) * item.quantity, 2)
                writer.writerow([
                    o.order_id if idx == 0 else "",
                    o.customer_name if idx == 0 else "",
                    (o.delivery_date or "") if idx == 0 else "",
                    item.product.name,
                    item.quantity,
                    f"{item.unit_price:.2f}",
                    f"{line_total:.2f}",
                    f"{order_comm:.2f}" if idx == 0 else "",
                    f"{order_net:.2f}" if idx == 0 else "",
                ])

        writer.writerow([])
        writer.writerow([
            "", "", "", "SETTLEMENT TOTAL",
            f"{settlement.gross_amount:.2f}",
            f"{settlement.commission_amount:.2f}",
            f"{settlement.net_amount:.2f}",
        ])
        return response

    def get(self, request):
        producer = request.user

        if request.GET.get("export") == "csv":
            settlement_ref = request.GET.get("settlement")
            if settlement_ref:
                return self._settlement_csv(producer, settlement_ref)

            # Full payment history CSV
            data = self._build_payment_data(producer)
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

        data = self._build_payment_data(producer)
        return render(request, self.template_name, {
            "payments": data["summary"],
            "pending_orders": data["pending_orders"],
            "all_orders": data["orders"],
            "settlements": data["settlements"],
            "tax_year": data["tax_year"],
            "tax_year_net": data["tax_year_net"],
            "tax_year_gross": data["tax_year_gross"],
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
            "pending_products": Product.objects.filter(status="Pending Approval").count(),
            "pending_users": User.objects.filter(
                status="suspended",
                account_type__in=["community_group", "restaurant"],
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


class AdminProductApprovalView(AdminRequiredMixin, View):
    template_name = "admin_panel/product_approval.html"

    def get(self, request):
        pending = Product.objects.filter(
            status="Pending Approval"
        ).select_related("producer").order_by("name")
        return render(request, self.template_name, {"pending_products": pending})

    def post(self, request):
        product_id = request.POST.get("product_id", "")
        action = request.POST.get("action", "")
        reject_reason = request.POST.get("reject_reason", "").strip()

        if not str(product_id).isdigit():
            messages.error(request, "Invalid product.")
            return redirect("/admin-panel/products/")

        product = get_object_or_404(Product, pk=int(product_id), status="Pending Approval")

        if action == "approve":
            product.status = "Available" if product.stock > 0 else "Out of Stock"
            product.save()
            send_email(
                product.producer.email,
                "Your product has been approved – DESD",
                (
                    f"Hi {product.producer.full_name},\n\n"
                    f"Your product '{product.name}' has been approved and is now live on the marketplace.\n\n"
                    "The DESD Team"
                ),
            )
            messages.success(request, f"'{product.name}' approved and is now live.")
        elif action == "reject":
            product.status = "Rejected"
            product.save()
            body = (
                f"Hi {product.producer.full_name},\n\n"
                f"Your product '{product.name}' was not approved and will not appear in the marketplace."
            )
            if reject_reason:
                body += f"\n\nReason: {reject_reason}"
            body += "\n\nPlease update the product and resubmit.\n\nThe DESD Team"
            send_email(
                product.producer.email,
                "Your product requires changes – DESD",
                body,
            )
            messages.warning(request, f"'{product.name}' rejected.")
        else:
            messages.error(request, "Unknown action.")

        return redirect("/admin-panel/products/")


class AdminUserApprovalView(AdminRequiredMixin, View):
    template_name = "admin_panel/user_approval.html"

    def get(self, request):
        pending = User.objects.filter(
            status="suspended",
            account_type__in=["community_group", "restaurant"],
        ).order_by("date_joined")
        return render(request, self.template_name, {"pending_users": pending})

    def post(self, request):
        user_id = request.POST.get("user_id", "")
        action = request.POST.get("action", "")
        reject_reason = request.POST.get("reject_reason", "").strip()

        if not str(user_id).isdigit():
            messages.error(request, "Invalid user.")
            return redirect("/admin-panel/users/approval/")

        user = get_object_or_404(
            User, pk=int(user_id), status="suspended",
            account_type__in=["community_group", "restaurant"],
        )

        if action == "approve":
            user.status = "active"
            user.save()
            send_email(
                user.email,
                "Your DESD account has been approved",
                (
                    f"Hi {user.full_name},\n\n"
                    "Your account has been approved and you can now log in to the DESD marketplace.\n\n"
                    "The DESD Team"
                ),
            )
            messages.success(request, f"{user.full_name} approved and can now log in.")
        elif action == "reject":
            body = (
                f"Hi {user.full_name},\n\n"
                "Unfortunately your account application has not been approved."
            )
            if reject_reason:
                body += f"\n\nReason: {reject_reason}"
            body += "\n\nThe DESD Team"
            send_email(
                user.email,
                "Your DESD account application",
                body,
            )
            user.delete()
            messages.warning(request, f"{user.full_name}'s application rejected and removed.")
        else:
            messages.error(request, "Unknown action.")

        return redirect("/admin-panel/users/approval/")


class AdminDeleteUserView(AdminRequiredMixin, View):
    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        if user.role == "admin":
            messages.error(request, "Admin accounts cannot be deleted.")
            return redirect("/admin-panel/users/")
        name = user.full_name or user.email
        user.delete()
        messages.success(request, f"{name}'s account has been deleted.")
        return redirect("/admin-panel/users/")


class DeleteAccountView(LoginRequiredMixin, View):
    def post(self, request):
        user = request.user
        if user.role == "admin":
            messages.error(request, "Admin accounts cannot be deleted.")
            return redirect("/")
        logout(request)
        user.delete()
        messages.success(request, "Your account has been deleted.")
        return redirect("/")


class AdminTestEmailView(AdminRequiredMixin, View):
    def get(self, request):
        to = request.GET.get("to", "").strip()
        if not to:
            from django.http import JsonResponse
            return JsonResponse({"error": "Provide ?to=email@example.com"}, status=400)
        from django.http import JsonResponse
        ok = send_email(
            to_email=to,
            subject="DESD SendGrid Test",
            body="This is a test email from DESD. If you received it, SendGrid is configured correctly.",
        )
        if ok:
            return JsonResponse({"status": "sent", "to": to})
        return JsonResponse({"status": "failed — check logs (SENDGRID_API_KEY may not be set or SendGrid returned an error)", "to": to}, status=500)


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

        # ── Override: producer disputes the AI grade ──────────────────────────
        if action == "override_grade":
            assessment_id = request.POST.get("assessment_id")
            override_grade = request.POST.get("override_grade", "").strip()
            reason = request.POST.get("reason", "other").strip()
            notes = request.POST.get("notes", "").strip()

            if not assessment_id or not str(assessment_id).isdigit():
                messages.error(request, "Missing assessment reference.")
                return redirect("/producer/quality-check/")

            if override_grade not in ("A", "B", "C"):
                messages.error(request, "Invalid grade — choose A, B or C.")
                return redirect("/producer/quality-check/")

            assessment = get_object_or_404(
                QualityAssessment,
                id=int(assessment_id),
                product__producer=request.user,
            )

            QualityOverride.objects.create(
                assessment=assessment,
                producer=request.user,
                ai_grade=assessment.grade,
                override_grade=override_grade,
                reason=reason,
                notes=notes,
            )
            messages.success(
                request,
                f"Override recorded: AI said Grade {assessment.grade}, "
                f"you marked Grade {override_grade}. "
                "This feedback will be used to improve the model."
            )
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
                # Price recommendation + waste risk after each quality check
                from app.services.forecast_service import get_demand_forecast
                from app.services.price_service import recommend_price
                from app.services.waste_service import compute_waste_risk
                fc = get_demand_forecast(product.id, weeks=1)
                result["price_recommendation"] = recommend_price(
                    product, result["grade"], fc.get("high_demand", False)
                )
                result["waste_risk"] = compute_waste_risk(product)
            except Product.DoesNotExist:
                pass
            except Exception:
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
        from app.services.quality_service import (
            load_latest_model_metrics,
            find_confusion_matrix_path,
        )


        ctx = super().get_context_data(**kwargs)
        ctx["stats"] = get_ai_monitoring_stats()
        ctx["recent_assessments"] = (
            QualityAssessment.objects
            .select_related("product", "assessed_by")
            .order_by("-assessed_at")[:20]
        )
        metrics = load_latest_model_metrics()
        if metrics is not None:
            ctx["model_metrics"] = metrics
        ctx["has_confusion_matrix"] = find_confusion_matrix_path() is not None
        from api.models import ModelEvaluation
        ctx["eval_history"] = list(
            ModelEvaluation.objects.values(
                "version", "accuracy", "precision", "recall", "f1_score", "evaluated_at"
            ).order_by("evaluated_at")
        )
        return ctx


class AdminAIAssessmentDetailView(AdminRequiredMixin, View):
    """Shows XAI heatmap + explanation for a single quality assessment.
    Admins can also submit a grade override directly from this page."""
    template_name = "admin_panel/ai_assessment_detail.html"

    def _get_assessment(self, pk):
        return get_object_or_404(
            QualityAssessment.objects.select_related("product", "assessed_by"),
            pk=pk,
        )

    def _build_xai(self, assessment):
        try:
            from ml.inference import classify_image
            with open(assessment.image.path, "rb") as f:
                image_bytes = f.read()
            result = classify_image(image_bytes, explain=True)
            return result.get("xai_heatmap"), result.get("xai_explanation")
        except Exception:
            return None, None

    def get(self, request, pk):
        assessment = self._get_assessment(pk)
        xai_heatmap, xai_explanation = self._build_xai(assessment)
        overrides = assessment.overrides.select_related("producer").order_by("-created_at")

        # Override rate for this product
        product = assessment.product
        total_for_product = QualityAssessment.objects.filter(product=product).count()
        overrides_for_product = QualityOverride.objects.filter(assessment__product=product).count()
        override_rate = round(overrides_for_product / total_for_product * 100) if total_for_product else 0

        return render(request, self.template_name, {
            "assessment": assessment,
            "xai_heatmap": xai_heatmap,
            "xai_explanation": xai_explanation,
            "overrides": overrides,
            "override_rate": override_rate,
            "overrides_for_product": overrides_for_product,
            "total_for_product": total_for_product,
        })

    def post(self, request, pk):
        assessment = self._get_assessment(pk)
        override_grade = request.POST.get("override_grade", "").strip()
        reason = request.POST.get("reason", "other").strip()
        notes = request.POST.get("notes", "").strip()

        if override_grade not in ("A", "B", "C"):
            messages.error(request, "Invalid grade — choose A, B or C.")
        else:
            QualityOverride.objects.create(
                assessment=assessment,
                producer=request.user,
                ai_grade=assessment.grade,
                override_grade=override_grade,
                reason=reason,
                notes=notes,
            )
            messages.success(
                request,
                f"Admin override recorded: AI={assessment.grade} → Override={override_grade}."
            )
        return redirect("admin_ai_assessment_detail", pk=pk)


class AdminModelUploadView(AdminRequiredMixin, View):
    """Allow AI engineers (admin role) to replace the active ML model.

    Routing by extension:
      .pth → EfficientNet-B0 checkpoint  (fruit_quality_ai/checkpoints/best_model.pth)
      .pt  → legacy MobileNetV2           (ml/saved_models/quality_classifier.pt)
    """

    _BACKEND_ROOT = pathlib.Path(__file__).resolve().parent.parent

    def post(self, request):
        uploaded = request.FILES.get("model_file")
        if not uploaded:
            messages.error(request, "No file uploaded.")
            return redirect("admin_ai_monitoring")

        name = uploaded.name
        if name.endswith(".pth"):
            model_path = self._BACKEND_ROOT / "fruit_quality_ai" / "checkpoints" / "best_model.pth"
            backup_path = model_path.with_name("best_model_prev.pth")
            version_prefix = "efficientnet-b0"
            cache_attrs = ("_fruit_predictor",)
        elif name.endswith(".pt"):
            model_path = self._BACKEND_ROOT / "ml" / "saved_models" / "quality_classifier.pt"
            backup_path = model_path.with_name("quality_classifier_prev.pt")
            version_prefix = "mobilenetv2"
            cache_attrs = ("_legacy_model",)
        else:
            messages.error(request, "Only .pth (EfficientNet) or .pt (MobileNet) files are accepted.")
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

        model_path.parent.mkdir(parents=True, exist_ok=True)
        if model_path.exists():
            import shutil
            shutil.copy2(model_path, backup_path)

        with open(model_path, "wb") as f:
            f.write(model_bytes)

        # Save optional metrics JSON (e.g., train/val accuracy from external training).
        metrics_file = request.FILES.get("metrics_file")
        if metrics_file and metrics_file.name.endswith(".json"):
            metrics_target = self._BACKEND_ROOT / "ml" / "saved_models" / "model_metrics.json"
            metrics_target.parent.mkdir(parents=True, exist_ok=True)
            with open(metrics_target, "wb") as f:
                f.write(metrics_file.read())

        # Clear in-process caches so the next inference loads the new file.
        import ml.inference as _inf
        for attr in cache_attrs:
            if hasattr(_inf, attr):
                setattr(_inf, attr, None)

        base = name.rsplit(".", 1)[0]
        version_label = base or f"{version_prefix}-v2"

        try:
            from api.tasks import evaluate_model_after_upload
            evaluate_model_after_upload.delay(version_label, arch=version_prefix)
        except Exception:
            logger.exception("Failed to enqueue evaluate_model_after_upload")

        messages.success(
            request,
            f"Model '{name}' uploaded and activated. "
            "Evaluation is running in the background — refresh this page in ~30 seconds to see updated metrics.",
        )
        return redirect("admin_ai_monitoring")


class AdminInteractionExportView(AdminRequiredMixin, View):
    """Export all QualityAssessment interaction records as CSV for model refinement.
    Override columns are included so the file can serve directly as retraining data."""

    def get(self, request):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="ai_interactions.csv"'
        writer = csv.writer(response)
        writer.writerow([
            "id", "product_name", "producer_email", "grade",
            "color_score", "size_score", "ripeness_score",
            "model_confidence", "model_version", "is_healthy",
            "notes", "quantity_lost", "assessed_at", "image_path",
            # Override columns (blank when no override exists)
            "override_grade", "override_reason", "override_notes",
            "overridden_by", "overridden_at",
        ])
        qs = (
            QualityAssessment.objects
            .select_related("product", "assessed_by")
            .prefetch_related("overrides__producer")
            .order_by("-assessed_at")
        )
        for a in qs:
            # Use the most recent override if multiple exist
            override = a.overrides.order_by("-created_at").first()
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
                override.override_grade if override else "",
                override.reason if override else "",
                override.notes.replace("\n", " ") if override else "",
                override.producer.email if override else "",
                override.created_at.isoformat() if override else "",
            ])
        return response


class AdminConfusionMatrixView(AdminRequiredMixin, View):
    """Serves the confusion_matrix.png from whichever evaluator wrote one.
    Prefers fruit_quality_ai/results/, falls back to ml/saved_models/."""

    def get(self, request):
        from app.services.quality_service import find_confusion_matrix_path
        cm_path = find_confusion_matrix_path()
        if cm_path is None:
            return HttpResponse(
                "Confusion matrix not found. Run `python fruit_quality_ai/main.py --mode evaluate` "
                "or `python -m ml.evaluate`.",
                status=404,
            )
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


# ── TC-018: Recurring orders ──────────────────────────────────────────────────

class RecurringOrdersView(CustomerRequiredMixin, View):
    template_name = "customer/recurring_orders.html"

    def get(self, request):
        orders = RecurringOrder.objects.filter(customer=request.user)
        pending_notifications = RecurringOrderNotification.objects.filter(
            recurring_order__customer=request.user,
            requires_action=True,
        ).select_related("recurring_order")
        # Mark non-action notifications as read when page is visited
        RecurringOrderNotification.objects.filter(
            recurring_order__customer=request.user,
            requires_action=False,
            is_read=False,
        ).update(is_read=True)
        return render(request, self.template_name, {
            "recurring_orders": orders,
            "pending_notifications": pending_notifications,
            "pending_notification_count": pending_notifications.count(),
        })

    def post(self, request):
        """Create a recurring order from current cart."""
        cart = request.session.get("cart", [])
        if not cart:
            messages.error(request, "Your cart is empty.")
            return redirect("recurring_orders")

        recurrence = request.POST.get("recurrence", "weekly")
        delivery_day = int(request.POST.get("delivery_day", 2))
        notes = request.POST.get("notes", "")
        end_date_str = request.POST.get("end_date", "").strip()
        on_price_change = request.POST.get("on_price_change", "")
        on_quantity_change = request.POST.get("on_quantity_change", "")

        if not end_date_str:
            messages.error(request, "An end date is required for recurring orders.")
            return redirect("recurring_orders")

        valid_prefs = {RecurringOrder.PREF_AUTO, RecurringOrder.PREF_NOTIFY}
        if on_price_change not in valid_prefs or on_quantity_change not in valid_prefs:
            messages.error(request, "Please answer both preference questions before continuing.")
            return redirect("recurring_orders")

        try:
            end_date = date.fromisoformat(end_date_str)
        except ValueError:
            messages.error(request, "Invalid end date format.")
            return redirect("recurring_orders")

        if end_date <= date.today():
            messages.error(request, "End date must be in the future.")
            return redirect("recurring_orders")

        today = date.today()
        days_ahead = (delivery_day - today.weekday()) % 7 or 7
        next_date = today + timedelta(days=days_ahead)
        RecurringOrder.objects.create(
            customer=request.user,
            items=cart,
            recurrence=recurrence,
            delivery_day=delivery_day,
            is_active=True,
            status=RecurringOrder.STATUS_ACTIVE,
            on_price_change=on_price_change,
            on_quantity_change=on_quantity_change,
            end_date=end_date,
            next_order_date=next_date,
            notes=notes,
        )
        messages.success(request, "Recurring order set up successfully!")
        return redirect("recurring_orders")


class CancelRecurringOrderView(CustomerRequiredMixin, View):
    """Cancel a recurring order permanently."""

    def post(self, request, pk):
        ro = get_object_or_404(RecurringOrder, pk=pk, customer=request.user)
        ro.is_active = False
        ro.status = RecurringOrder.STATUS_CANCELLED
        ro.save(update_fields=["is_active", "status"])
        messages.success(request, "Recurring order cancelled.")
        return redirect("recurring_orders")


class RecurringOrderNotificationsView(CustomerRequiredMixin, View):
    """List all notifications for the logged-in customer's recurring orders."""

    template_name = "customer/recurring_notifications.html"

    def get(self, request):
        notifications = RecurringOrderNotification.objects.filter(
            recurring_order__customer=request.user,
        ).select_related("recurring_order")
        # Mark all as read when the page is opened
        RecurringOrderNotification.objects.filter(
            recurring_order__customer=request.user,
            is_read=False,
        ).update(is_read=True)
        return render(request, self.template_name, {"notifications": notifications})


class RecurringOrderApproveView(CustomerRequiredMixin, View):
    """Handle customer approval or rejection of a paused recurring order notification."""

    def post(self, request, pk):
        notification = get_object_or_404(
            RecurringOrderNotification,
            pk=pk,
            recurring_order__customer=request.user,
            requires_action=True,
        )
        action = request.POST.get("action")
        ro = notification.recurring_order

        if action == "approve":
            # If price changed, update stored prices to current market price
            if notification.notification_type == RecurringOrderNotification.TYPE_PRICE:
                updated_items = []
                product_ids = [int(i["product_id"]) for i in ro.items]
                products_map = {p.id: p for p in Product.objects.filter(pk__in=product_ids)}
                for item in ro.items:
                    product = products_map.get(int(item["product_id"]))
                    if product:
                        item = dict(item)
                        item["price"] = float(product.price)
                    updated_items.append(item)
                ro.items = updated_items

            ro.status = RecurringOrder.STATUS_ACTIVE
            ro.pause_reason = ""
            ro.is_active = True
            ro.save(update_fields=["status", "pause_reason", "is_active", "items"])
            notification.action_taken = RecurringOrderNotification.ACTION_APPROVED
            notification.requires_action = False
            notification.is_read = True
            notification.save()
            messages.success(request, "Recurring order resumed.")
        else:
            # Rejected — keep paused, mark notification handled
            notification.action_taken = RecurringOrderNotification.ACTION_REJECTED
            notification.requires_action = False
            notification.is_read = True
            notification.save()
            messages.info(request, "Recurring order remains paused. Cancel it if you no longer want it.")

        return redirect("recurring_orders")


# ── TC-020: Recipes & Farm Stories ───────────────────────────────────────────

class ProducerRecipesView(ProducerRequiredMixin, View):
    template_name = "producer/recipes.html"

    def _render(self, request, form=None, story_form=None):
        recipes = Recipe.objects.filter(producer=request.user)
        stories = FarmStory.objects.filter(producer=request.user)
        products = Product.objects.filter(producer=request.user, status__in=["Available", "In Season"])
        return render(request, self.template_name, {
            "recipes": recipes,
            "stories": stories,
            "products": products,
            "form": form or RecipeForm(),
            "story_form": story_form or FarmStoryForm(),
        })

    def get(self, request):
        return self._render(request)

    def post(self, request):
        if "add_story" in request.POST:
            form = FarmStoryForm(request.POST)
            if form.is_valid():
                story = form.save(commit=False)
                story.producer = request.user
                story.save()
                messages.success(request, "Farm story published!")
                return redirect("producer_content")
            return self._render(request, story_form=form)
        else:
            form = RecipeForm(request.POST)
            if form.is_valid():
                recipe = form.save(commit=False)
                recipe.producer = request.user
                recipe.save()
                product_ids = request.POST.getlist("linked_products")
                if product_ids:
                    recipe.products.set(Product.objects.filter(id__in=product_ids, producer=request.user))
                messages.success(request, "Recipe published!")
                return redirect("producer_content")
            return self._render(request, form=form)


class RecipeDetailView(View):
    def get(self, request, pk):
        recipe = get_object_or_404(Recipe, pk=pk)
        return render(request, "producer/recipe_detail.html", {"recipe": recipe})


# ── TC-030: Demand forecast ───────────────────────────────────────────────────

class ProducerDemandForecastView(ProducerRequiredMixin, View):
    """
    JSON demand forecast endpoint for a producer's products.

    Forecast values come from the SARIMA-backed service in
    app/services/forecast_service.py (which falls back to a moving average
    when the trained model file is absent). This view then overlays the
    product's harvest-season window so the frontend can flag out-of-season
    items. One canonical forecast implementation, not two.
    """

    def get(self, request):
        from collections import defaultdict
        from calendar import month_abbr
        from app.services.forecast_service import get_demand_forecast

        producer = request.user
        today = date.today()
        six_months_ago = today.replace(day=1) - timedelta(days=180)

        products = Product.objects.filter(producer=producer).order_by("name")
        result = []

        for product in products:
            # Recent monthly history (unchanged — used by the chart).
            items = (
                OrderItem.objects.filter(
                    product=product,
                    order__status="Delivered",
                    order__delivery_date__gte=six_months_ago,
                ).select_related("order")
            )
            monthly: dict[str, int] = defaultdict(int)
            for item in items:
                if item.order.delivery_date:
                    key = item.order.delivery_date.strftime("%Y-%m")
                    monthly[key] += item.quantity

            # Delegate forecast computation to the shared service — keeps a
            # single source of truth for "what the next month looks like".
            try:
                fc = get_demand_forecast(product.id, weeks=4)
                forecast = round(sum(fc["predicted_units"])) if fc.get("predicted_units") else 0
            except Exception:
                logger.exception("get_demand_forecast failed for product %s", product.id)
                forecast = 0

            # Harvest-season overlay (forecast service has no season knowledge).
            in_season = True
            season_label = "Year round"
            if product.season_start and product.season_end:
                start_md = (product.season_start.month, product.season_start.day)
                end_md = (product.season_end.month, product.season_end.day)
                today_md = (today.month, today.day)
                if start_md <= end_md:
                    in_season = start_md <= today_md <= end_md
                else:
                    in_season = today_md >= start_md or today_md <= end_md
                season_label = (
                    f"{month_abbr[product.season_start.month]} – "
                    f"{month_abbr[product.season_end.month]}"
                )

            result.append({
                "id": product.id,
                "name": product.name,
                "category": product.category,
                "current_stock": product.stock,
                "monthly_orders": dict(sorted(monthly.items())),
                "forecast_next_month": forecast,
                "in_season": in_season,
                "season_label": season_label,
            })

        return JsonResponse({"products": result})


# ── TC-031: Admin override review ─────────────────────────────────────────────

class AdminOverrideReviewView(AdminRequiredMixin, View):
    """
    Admin view showing all producer grade overrides for fairness monitoring.

    If one producer consistently overrides in one direction, that may signal
    systematic model bias against their produce type, warranting investigation.
    """

    def get(self, request):
        overrides = (
            QualityOverride.objects
            .select_related("assessment__product", "producer")
            .order_by("-created_at")[:200]
        )
        producer_counts = list(
            QualityOverride.objects
            .values("producer__full_name", "producer__email")
            .annotate(count=Count("id"))
            .order_by("-count")[:10]
        )
        return render(request, "admin_panel/override_review.html", {
            "overrides": overrides,
            "producer_counts": producer_counts,
            "total_overrides": QualityOverride.objects.count(),
        })


# ── Error views ───────────────────────────────────────────────────────────────

def view_401(request):
    return render(request, "errors/401.html", status=401)


def view_403(request):
    return render(request, "errors/403.html", status=403)


def view_404(request, exception=None):
    return render(request, "errors/404.html", status=404)
