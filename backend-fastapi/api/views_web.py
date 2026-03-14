"""
Django template-based views for the DESD web application.

Uses Django's MVT pattern:
  - Models  → api/models.py
  - Views   → this file (class-based and function-based views)
  - Templates → api/templates/
"""

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import (
    CreateView,
    DetailView,
    FormView,
    ListView,
    TemplateView,
    UpdateView,
)

from api.forms import (
    CheckoutForm,
    LoginForm,
    OrderStatusForm,
    ProductForm,
    ReportFilterForm,
    RegisterForm,
)
from api.models import Order, Product, User
from app.repositories.auth_repo import find_user_by_email
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


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ud(user) -> dict:
    """Convert a Django User object into the dict the service layer expects."""
    return {"email": user.email, "role": user.role, "full_name": user.full_name}


# ── Role-enforcement mixins ───────────────────────────────────────────────────

class _RoleMixin(LoginRequiredMixin, UserPassesTestMixin):
    login_url = "/login/"
    _required_role: str = ""

    def test_func(self):
        return self.request.user.role == self._required_role

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return redirect("/login/")
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


class MarketplaceView(TemplateView):
    template_name = "marketplace.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["products"] = Product.objects.filter(status="Available").order_by("name")[:12]
        ctx["categories"] = list(
            Product.objects.values_list("category", flat=True).distinct()
        )
        try:
            ctx["recommendations"] = recommend_products(limit=4)
        except Exception:
            ctx["recommendations"] = []
        if self.request.user.is_authenticated and self.request.user.role == "customer":
            try:
                ctx["customer_data"] = customer_summary(_ud(self.request.user))
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


# ── Authentication views ──────────────────────────────────────────────────────

class LoginPageView(View):
    template_name = "login.html"

    def get(self, request):
        if request.user.is_authenticated:
            return redirect("/")
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
                return redirect(request.GET.get("next", "/"))
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
            if find_user_by_email(email):
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


# ── Customer views ─────────────────────────────────────────────────────────────

class CustomerDashboardView(CustomerRequiredMixin, TemplateView):
    template_name = "customer/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["summary"] = customer_summary(_ud(self.request.user))
        return ctx


class ProductListView(CustomerRequiredMixin, ListView):
    template_name = "customer/products.html"
    context_object_name = "products"

    def get_queryset(self):
        qs = Product.objects.filter(status="Available")
        q = self.request.GET.get("q", "")
        category = self.request.GET.get("category", "")
        if q:
            qs = qs.filter(name__icontains=q)
        if category:
            qs = qs.filter(category=category)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["categories"] = list(
            Product.objects.values_list("category", flat=True).distinct()
        )
        ctx["q"] = self.request.GET.get("q", "")
        ctx["selected_category"] = self.request.GET.get("category", "")
        return ctx


class CartView(CustomerRequiredMixin, TemplateView):
    template_name = "customer/cart.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        cart = self.request.session.get("cart", [])
        ctx["cart"] = cart
        ctx["total"] = round(sum(float(i["price"]) * int(i["quantity"]) for i in cart), 2)
        return ctx


class AddToCartView(CustomerRequiredMixin, View):
    def post(self, request, product_id):
        product = get_object_or_404(Product, pk=product_id, status="Available")
        cart = request.session.get("cart", [])
        for item in cart:
            if item["product_id"] == product_id:
                item["quantity"] += 1
                request.session["cart"] = cart
                messages.success(request, f"Added another {product.name} to cart.")
                return redirect("/products/")
        cart.append({
            "product_id": product_id,
            "name": product.name,
            "price": float(product.price),
            "quantity": 1,
        })
        request.session["cart"] = cart
        messages.success(request, f"{product.name} added to cart.")
        return redirect("/products/")


class RemoveFromCartView(CustomerRequiredMixin, View):
    def post(self, request, product_id):
        cart = request.session.get("cart", [])
        request.session["cart"] = [i for i in cart if i["product_id"] != product_id]
        messages.info(request, "Item removed from cart.")
        return redirect("/cart/")


class CheckoutView(CustomerRequiredMixin, View):
    template_name = "customer/checkout.html"

    def get(self, request):
        cart = request.session.get("cart", [])
        total = round(sum(float(i["price"]) * int(i["quantity"]) for i in cart), 2)
        return render(request, self.template_name, {
            "form": CheckoutForm(),
            "cart": cart,
            "total": total,
        })

    def post(self, request):
        form = CheckoutForm(request.POST)
        cart = request.session.get("cart", [])
        total = round(sum(float(i["price"]) * int(i["quantity"]) for i in cart), 2)
        if form.is_valid():
            form.save()
            request.session["cart"] = []
            messages.success(request, "Order placed successfully! We will contact you shortly.")
            return redirect("/customer/")
        return render(request, self.template_name, {"form": form, "cart": cart, "total": total})


# ── Producer views ─────────────────────────────────────────────────────────────

class ProducerDashboardView(ProducerRequiredMixin, TemplateView):
    template_name = "producer/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["summary"] = producer_summary(_ud(self.request.user))
        return ctx


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
        if form.is_valid():
            try:
                create_producer_product(_ud(request.user), form.cleaned_data)
                messages.success(request, "Product created successfully.")
                return redirect("/producer/products/")
            except (ValueError, LookupError) as exc:
                messages.error(request, str(exc))
        return self._render(request, form=form)


class ProducerProductEditView(ProducerRequiredMixin, View):
    template_name = "producer/product_edit.html"

    def _get_product(self, request, pk):
        return get_object_or_404(Product, pk=pk, producer=request.user)

    def get(self, request, pk):
        product = self._get_product(request, pk)
        form = ProductForm(instance=product)
        return render(request, self.template_name, {"form": form, "product": product})

    def post(self, request, pk):
        product = self._get_product(request, pk)
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            try:
                update_producer_product(_ud(request.user), pk, form.cleaned_data)
                messages.success(request, "Product updated.")
                return redirect("/producer/products/")
            except (LookupError, PermissionError, ValueError) as exc:
                messages.error(request, str(exc))
        return render(request, self.template_name, {"form": form, "product": product})


class ProducerOrdersView(ProducerRequiredMixin, TemplateView):
    template_name = "producer/orders.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        data = producer_orders(_ud(self.request.user))
        ctx["orders"] = data.get("items", [])
        ctx["status_choices"] = ["Pending", "Confirmed", "Ready", "Delivered"]
        return ctx


class ProducerOrderDetailView(ProducerRequiredMixin, TemplateView):
    template_name = "producer/order_detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        try:
            ctx["order"] = producer_order_detail(_ud(self.request.user), self.kwargs["order_id"])
        except LookupError:
            ctx["order"] = None
        return ctx


class ProducerOrderStatusUpdateView(ProducerRequiredMixin, View):
    def post(self, request, order_id):
        form = OrderStatusForm(request.POST)
        if form.is_valid():
            try:
                update_producer_order_status(
                    _ud(request.user), order_id, form.cleaned_data["status"]
                )
                messages.success(request, "Order status updated.")
            except (LookupError, ValueError) as exc:
                messages.error(request, str(exc))
        return redirect("/producer/orders/")


class ProducerPaymentsView(ProducerRequiredMixin, TemplateView):
    template_name = "producer/payments.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["payments"] = producer_payments(_ud(self.request.user))
        return ctx


# ── Admin views ────────────────────────────────────────────────────────────────

class AdminDashboardView(AdminRequiredMixin, TemplateView):
    template_name = "admin_panel/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["summary"] = admin_summary(_ud(self.request.user))
        return ctx


class AdminReportsView(AdminRequiredMixin, View):
    template_name = "admin_panel/reports.html"

    def get(self, request):
        form = ReportFilterForm(request.GET or None)
        rows = []
        date_from = None
        date_to = None
        if form.is_valid():
            df = form.cleaned_data.get("date_from")
            dt = form.cleaned_data.get("date_to")
            date_from = str(df) if df else None
            date_to = str(dt) if dt else None
        data = admin_reports(_ud(request.user), date_from=date_from, date_to=date_to)
        rows = data.get("rows", [])
        total_orders = sum(r.get("orders", 0) for r in rows)
        total_gross = round(sum(float(r.get("gross", 0)) for r in rows), 2)
        total_commission = round(sum(float(r.get("commission", 0)) for r in rows), 2)
        return render(request, self.template_name, {
            "form": form,
            "rows": rows,
            "total_orders": total_orders,
            "total_gross": total_gross,
            "total_commission": total_commission,
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
        data = admin_database(_ud(self.request.user))
        ctx["db_users"] = data.get("users", [])
        ctx["db_products"] = data.get("products", [])
        ctx["db_orders"] = data.get("orders", [])
        return ctx


# ── Error views ───────────────────────────────────────────────────────────────

def view_401(request):
    return render(request, "errors/401.html", status=401)


def view_403(request):
    return render(request, "errors/403.html", status=403)


def view_404(request, exception=None):
    return render(request, "errors/404.html", status=404)
