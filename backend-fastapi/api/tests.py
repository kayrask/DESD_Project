"""
Automated tests for the checkout flow.

Run with:  python manage.py test api
"""
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase, Client
from django.urls import reverse

from api.models import CheckoutOrder, CommissionReport, Order, OrderItem, Product, User
from app.core.security import issue_token


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_customer(email="customer@test.com", password="Test1234"):
    return User.objects.create_user(
        email=email,
        password=password,
        full_name="Test Customer",
        role="customer",
    )


def _make_producer(email="producer@test.com"):
    return User.objects.create_user(
        email=email,
        password="Test1234",
        full_name="Test Producer",
        role="producer",
    )


def _make_product(producer, name="Apple", price="2.00", stock=10):
    return Product.objects.create(
        name=name,
        category="Fruit",
        price=Decimal(price),
        stock=stock,
        status="Available",
        producer=producer,
    )


def _valid_date():
    """Return a delivery date that passes the 48-hour rule."""
    return (date.today() + timedelta(days=3)).isoformat()


def _invalid_date():
    """Return a delivery date that fails the 48-hour rule (tomorrow)."""
    return (date.today() + timedelta(days=1)).isoformat()


# ── TC-007: 48-hour delivery date rule ───────────────────────────────────────

class DeliveryDateValidationTest(TestCase):
    """
    TC-007 — Delivery date must be at least 2 days from today.
    A date < 48 h in the future must be rejected by the backend.
    """

    def setUp(self):
        self.client = Client()
        self.producer = _make_producer()
        self.customer = _make_customer()
        self.product = _make_product(self.producer)
        self.client.login(username="customer@test.com", password="Test1234")

        # Prime the session cart
        session = self.client.session
        session["cart"] = [{
            "product_id": self.product.id,
            "name": self.product.name,
            "price": float(self.product.price),
            "quantity": 1,
            "producer_id": self.producer.id,
            "producer_name": self.producer.full_name,
        }]
        session.save()

    def _post_checkout(self, delivery_date):
        return self.client.post(
            reverse("checkout"),
            {
                "full_name": "Test Customer",
                "email": "customer@test.com",
                "address": "123 Test Street",
                "city": "London",
                "postal_code": "SW1A 1AA",
                "payment_method": "card",
                "accept_terms": "on",
                "address_confirmed": "1",
                f"delivery_date_{self.producer.id}": delivery_date,
            },
        )

    def test_valid_delivery_date_creates_order(self):
        """A delivery date 3 days ahead should succeed and create a CheckoutOrder."""
        initial_count = CheckoutOrder.objects.count()
        response = self._post_checkout(_valid_date())
        self.assertEqual(CheckoutOrder.objects.count(), initial_count + 1)

    def test_invalid_delivery_date_rejected(self):
        """A delivery date only 1 day ahead must not create an order."""
        initial_count = CheckoutOrder.objects.count()
        self._post_checkout(_invalid_date())
        self.assertEqual(CheckoutOrder.objects.count(), initial_count,
                         "Order should NOT be created for a date < 48 h from now.")


# ── TC-008: Multi-producer checkout splits into separate vendor orders ────────

class MultiProducerCheckoutTest(TestCase):
    """
    TC-008 — A cart with items from two different producers must create two
    separate vendor Order records, each with its own delivery date.
    """

    def setUp(self):
        self.client = Client()
        self.producer_a = _make_producer("producer_a@test.com")
        self.producer_b = _make_producer("producer_b@test.com")
        self.customer = _make_customer()
        self.product_a = _make_product(self.producer_a, name="Apple", price="2.00")
        self.product_b = _make_product(self.producer_b, name="Mushroom", price="3.50")
        self.client.login(username="customer@test.com", password="Test1234")

        session = self.client.session
        session["cart"] = [
            {
                "product_id": self.product_a.id,
                "name": self.product_a.name,
                "price": float(self.product_a.price),
                "quantity": 2,
                "producer_id": self.producer_a.id,
                "producer_name": self.producer_a.full_name,
            },
            {
                "product_id": self.product_b.id,
                "name": self.product_b.name,
                "price": float(self.product_b.price),
                "quantity": 1,
                "producer_id": self.producer_b.id,
                "producer_name": self.producer_b.full_name,
            },
        ]
        session.save()

    def test_two_producer_orders_created(self):
        """Checkout with 2 producers → 2 vendor Order records."""
        date_a = (date.today() + timedelta(days=3)).isoformat()
        date_b = (date.today() + timedelta(days=5)).isoformat()

        self.client.post(
            reverse("checkout"),
            {
                "full_name": "Test Customer",
                "email": "customer@test.com",
                "address": "123 Test Street",
                "city": "London",
                "postal_code": "SW1A 1AA",
                "payment_method": "card",
                "accept_terms": "on",
                "address_confirmed": "1",
                f"delivery_date_{self.producer_a.id}": date_a,
                f"delivery_date_{self.producer_b.id}": date_b,
            },
        )
        # One CheckoutOrder should have been created
        self.assertEqual(CheckoutOrder.objects.count(), 1)
        # Two vendor Orders (one per producer) should exist
        self.assertEqual(Order.objects.count(), 2,
                         "Expected one vendor Order per producer.")

    def test_stock_decremented_after_checkout(self):
        """Stock must be reduced by the ordered quantity after successful checkout."""
        date_a = (date.today() + timedelta(days=3)).isoformat()
        date_b = (date.today() + timedelta(days=4)).isoformat()

        self.client.post(
            reverse("checkout"),
            {
                "full_name": "Test Customer",
                "email": "customer@test.com",
                "address": "123 Test Street",
                "city": "London",
                "postal_code": "SW1A 1AA",
                "payment_method": "card",
                "accept_terms": "on",
                "address_confirmed": "1",
                f"delivery_date_{self.producer_a.id}": date_a,
                f"delivery_date_{self.producer_b.id}": date_b,
            },
        )
        self.product_a.refresh_from_db()
        self.product_b.refresh_from_db()
        self.assertEqual(self.product_a.stock, 8,
                         "Product A stock should decrease by 2 (ordered qty).")
        self.assertEqual(self.product_b.stock, 9,
                         "Product B stock should decrease by 1 (ordered qty).")


# ── Producer product update validation (Sprint 2 Matthew scope) ─────────────

class ProducerProductUpdateValidationTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.producer = _make_producer("producer_update@test.com")
        self.product = _make_product(self.producer, name="Spinach", price="1.90", stock=12)
        self.token = issue_token(self.producer)

    def test_patch_product_rejects_negative_stock(self):
        response = self.client.patch(
            f"/producer/products/{self.product.id}",
            data={"stock": -1},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 400)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 12)

    def test_patch_product_rejects_invalid_status(self):
        response = self.client.patch(
            f"/producer/products/{self.product.id}",
            data={"status": "NotARealStatus"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 400)


# ── Admin reports pagination (Sprint 3 Matthew scope) ───────────────────────

class AdminReportsPaginationTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            email="admin_reports@test.com",
            password="Test1234",
            full_name="Admin Reports",
            role="admin",
        )
        self.client.login(username=self.admin.email, password="Test1234")

        for idx in range(15):
            CommissionReport.objects.create(
                report_date=date.today() - timedelta(days=idx),
                total_orders=idx + 1,
                gross_amount=Decimal("100.00") + idx,
                commission_amount=Decimal("5.00") + (Decimal(idx) / Decimal("10")),
            )

    def test_admin_reports_first_page_has_page_size(self):
        response = self.client.get(reverse("admin_reports"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("page_obj", response.context)
        self.assertEqual(len(response.context["rows"]), 10)
        self.assertEqual(response.context["page_obj"].number, 1)

    def test_admin_reports_second_page_has_remaining_rows(self):
        response = self.client.get(reverse("admin_reports"), {"page": 2})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["rows"]), 5)
        self.assertEqual(response.context["page_obj"].number, 2)
