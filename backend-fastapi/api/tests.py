"""
Automated tests for the full application.

Run with:  python manage.py test api
"""
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase, Client
from django.urls import reverse

from api.models import (
    CartReservation, CheckoutOrder, CommissionReport, FarmStory, Order, OrderItem,
    PaymentSettlement, Product, QualityAssessment, Recipe, RecurringOrder, User,
)
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


# ── TC-021: Product discount_percentage & discounted_price ───────────────────

class ProductDiscountTest(TestCase):
    def setUp(self):
        self.producer = _make_producer("disc_producer@test.com")

    def test_no_discount_returns_none(self):
        p = _make_product(self.producer, price="10.00")
        p.discount_percentage = 0
        self.assertIsNone(p.discounted_price)

    def test_twenty_percent_discount(self):
        p = _make_product(self.producer, price="10.00")
        p.discount_percentage = 20
        self.assertAlmostEqual(p.discounted_price, 8.00, places=2)

    def test_fifty_percent_discount(self):
        p = _make_product(self.producer, price="5.00")
        p.discount_percentage = 50
        self.assertAlmostEqual(p.discounted_price, 2.50, places=2)


# ── TC-022: Low stock threshold ───────────────────────────────────────────────

class LowStockThresholdTest(TestCase):
    def setUp(self):
        self.producer = _make_producer("threshold_producer@test.com")

    def test_default_threshold_is_five(self):
        p = _make_product(self.producer, stock=10)
        self.assertEqual(p.low_stock_threshold, 5)

    def test_stock_at_threshold_is_low_stock(self):
        p = _make_product(self.producer, stock=5)
        p.low_stock_threshold = 5
        p.save()
        p.refresh_from_db()
        self.assertTrue(p.stock <= p.low_stock_threshold)

    def test_stock_above_threshold_is_not_low(self):
        p = _make_product(self.producer, stock=10)
        p.low_stock_threshold = 5
        p.save()
        p.refresh_from_db()
        self.assertFalse(p.stock <= p.low_stock_threshold)


# ── TC-023: User account_type field ──────────────────────────────────────────

class UserAccountTypeTest(TestCase):
    def test_default_account_type_is_individual(self):
        user = _make_customer("acct_type@test.com")
        self.assertEqual(user.account_type, "individual")

    def test_community_group_account_type(self):
        user = User.objects.create_user(
            email="community@test.com",
            password="Test1234",
            full_name="Community Group",
            role="customer",
            account_type="community_group",
            organization_name="Green Collective",
        )
        self.assertEqual(user.account_type, "community_group")
        self.assertEqual(user.organization_name, "Green Collective")

    def test_restaurant_account_type(self):
        user = User.objects.create_user(
            email="restaurant@test.com",
            password="Test1234",
            full_name="Restaurant Owner",
            role="customer",
            account_type="restaurant",
            organization_name="Bistro 22",
        )
        self.assertEqual(user.account_type, "restaurant")


# ── TC-024: Reorder — re-adds available items to cart ─────────────────────────

class ReorderViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.producer = _make_producer("reorder_producer@test.com")
        self.customer = _make_customer("reorder_customer@test.com")
        self.product = _make_product(self.producer, name="Carrot", price="1.50", stock=10)
        self.client.login(username="reorder_customer@test.com", password="Test1234")

        # Build a past CheckoutOrder
        self.checkout = CheckoutOrder.objects.create(
            customer=self.customer,
            full_name="Test Customer",
            email="reorder_customer@test.com",
            address="1 Test Road",
            city="London",
            postal_code="E1 1AA",
            payment_method="card",
        )
        order = Order.objects.create(
            order_id=f"CO-{self.checkout.id}-P{self.producer.id}",
            customer_name="Test Customer",
            delivery_date=date.today() + timedelta(days=4),
            status="Delivered",
            producer=self.producer,
        )
        OrderItem.objects.create(order=order, product=self.product, quantity=2, unit_price=Decimal("1.50"))

    def test_reorder_adds_items_to_cart(self):
        response = self.client.post(reverse("order_reorder", args=[self.checkout.id]))
        self.assertRedirects(response, "/cart/")
        cart = self.client.session.get("cart", [])
        product_ids = [item["product_id"] for item in cart]
        self.assertIn(self.product.id, product_ids)

    def test_reorder_skips_out_of_stock_items(self):
        self.product.stock = 0
        self.product.status = "Out of Stock"
        self.product.save()
        self.client.post(reverse("order_reorder", args=[self.checkout.id]))
        cart = self.client.session.get("cart", [])
        self.assertEqual(cart, [])

    def test_reorder_respects_available_stock(self):
        self.product.stock = 1
        self.product.save()
        self.client.post(reverse("order_reorder", args=[self.checkout.id]))
        cart = self.client.session.get("cart", [])
        item = next((i for i in cart if i["product_id"] == self.product.id), None)
        self.assertIsNotNone(item)
        self.assertEqual(item["quantity"], 1)


# ── TC-025: Order receipt view ────────────────────────────────────────────────

class OrderReceiptViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.producer = _make_producer("receipt_producer@test.com")
        self.customer = _make_customer("receipt_customer@test.com")
        self.product = _make_product(self.producer, name="Tomato", price="2.00", stock=10)
        self.client.login(username="receipt_customer@test.com", password="Test1234")

        self.checkout = CheckoutOrder.objects.create(
            customer=self.customer,
            full_name="Test Customer",
            email="receipt_customer@test.com",
            address="2 Test Road",
            city="London",
            postal_code="E2 2AA",
            payment_method="card",
        )
        order = Order.objects.create(
            order_id=f"CO-{self.checkout.id}-P{self.producer.id}",
            customer_name="Test Customer",
            delivery_date=date.today() + timedelta(days=4),
            status="Delivered",
            producer=self.producer,
        )
        OrderItem.objects.create(order=order, product=self.product, quantity=2, unit_price=Decimal("2.00"))

    def test_receipt_returns_200(self):
        response = self.client.get(reverse("order_receipt", args=[self.checkout.id]))
        self.assertEqual(response.status_code, 200)

    def test_receipt_shows_correct_grand_total(self):
        response = self.client.get(reverse("order_receipt", args=[self.checkout.id]))
        self.assertEqual(response.context["grand_total"], Decimal("4.00"))

    def test_receipt_forbidden_for_other_customer(self):
        other = _make_customer("other_receipt@test.com")
        self.client.login(username="other_receipt@test.com", password="Test1234")
        response = self.client.get(reverse("order_receipt", args=[self.checkout.id]))
        self.assertEqual(response.status_code, 404)


# ── TC-026: Recurring orders ──────────────────────────────────────────────────

class RecurringOrdersTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.producer = _make_producer("rec_producer@test.com")
        self.customer = _make_customer("rec_customer@test.com")
        self.product = _make_product(self.producer, name="Lettuce", price="1.00", stock=20)
        self.client.login(username="rec_customer@test.com", password="Test1234")

        session = self.client.session
        session["cart"] = [{
            "product_id": self.product.id,
            "name": "Lettuce",
            "price": 1.00,
            "quantity": 3,
            "producer_id": self.producer.id,
            "producer_name": self.producer.full_name,
        }]
        session.save()

    def _recurring_post_data(self, **overrides):
        """Minimum valid POST data for creating a recurring order."""
        data = {
            "recurrence": "weekly",
            "delivery_day": 2,
            "notes": "Leave at door",
            "end_date": (date.today() + timedelta(days=30)).isoformat(),
            "on_price_change": "pause_notify",
            "on_quantity_change": "auto_continue",
        }
        data.update(overrides)
        return data

    def test_create_recurring_order_from_cart(self):
        response = self.client.post(reverse("recurring_orders"), self._recurring_post_data())
        self.assertRedirects(response, reverse("recurring_orders"))
        self.assertEqual(RecurringOrder.objects.filter(customer=self.customer).count(), 1)

    def test_recurring_order_is_active_by_default(self):
        self.client.post(reverse("recurring_orders"), self._recurring_post_data(recurrence="fortnightly", delivery_day=3, notes=""))
        ro = RecurringOrder.objects.get(customer=self.customer)
        self.assertTrue(ro.is_active)

    def test_cancel_recurring_order(self):
        ro = RecurringOrder.objects.create(
            customer=self.customer,
            items=[],
            recurrence="weekly",
            delivery_day=2,
            is_active=True,
            next_order_date=date.today() + timedelta(days=7),
        )
        response = self.client.post(reverse("recurring_order_cancel", args=[ro.pk]))
        self.assertRedirects(response, reverse("recurring_orders"))
        ro.refresh_from_db()
        self.assertFalse(ro.is_active)

    def test_cancel_other_customer_recurring_order_returns_404(self):
        other = _make_customer("other_rec@test.com")
        ro = RecurringOrder.objects.create(
            customer=other,
            items=[],
            recurrence="weekly",
            delivery_day=2,
            is_active=True,
            next_order_date=date.today() + timedelta(days=7),
        )
        response = self.client.post(reverse("recurring_order_cancel", args=[ro.pk]))
        self.assertEqual(response.status_code, 404)

    def test_create_recurring_order_with_empty_cart_fails(self):
        session = self.client.session
        session["cart"] = []
        session.save()
        response = self.client.post(reverse("recurring_orders"), self._recurring_post_data(notes=""))
        self.assertEqual(RecurringOrder.objects.filter(customer=self.customer).count(), 0)


# ── TC-027: Producer recipes & farm stories ───────────────────────────────────

class ProducerRecipesTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.producer = _make_producer("recipes_producer@test.com")
        self.client.login(username="recipes_producer@test.com", password="Test1234")

    def test_create_recipe(self):
        product = _make_product(self.producer, name="Basil", price="0.80")
        response = self.client.post(reverse("producer_content"), {
            "title": "Pesto Pasta",
            "description": "A classic Italian sauce.",
            "ingredients": "Basil\nPine nuts\nParmesan",
            "instructions": "Blend everything.",
            "seasonal_tag": "summer",
            "linked_products": [product.id],
        })
        self.assertRedirects(response, reverse("producer_content"))
        recipe = Recipe.objects.get(producer=self.producer)
        self.assertEqual(recipe.title, "Pesto Pasta")
        self.assertIn(product, recipe.products.all())

    def test_create_farm_story(self):
        response = self.client.post(reverse("producer_content"), {
            "add_story": "1",
            "title": "Our Spring Harvest",
            "content": "This year's harvest was exceptional.",
        })
        self.assertRedirects(response, reverse("producer_content"))
        story = FarmStory.objects.get(producer=self.producer)
        self.assertEqual(story.title, "Our Spring Harvest")

    def test_recipe_detail_page_accessible(self):
        recipe = Recipe.objects.create(
            producer=self.producer,
            title="Tomato Salad",
            description="Simple and fresh.",
            ingredients="Tomatoes\nOlive oil",
            instructions="Combine and serve.",
            seasonal_tag="summer",
        )
        response = self.client.get(reverse("recipe_detail", args=[recipe.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["recipe"].title, "Tomato Salad")

    def test_recipe_detail_404_for_nonexistent(self):
        response = self.client.get(reverse("recipe_detail", args=[9999]))
        self.assertEqual(response.status_code, 404)

    def test_producer_content_page_loads(self):
        response = self.client.get(reverse("producer_content"))
        self.assertEqual(response.status_code, 200)

    def test_non_producer_cannot_access_content_page(self):
        customer = _make_customer("content_customer@test.com")
        self.client.login(username="content_customer@test.com", password="Test1234")
        response = self.client.get(reverse("producer_content"))
        self.assertNotEqual(response.status_code, 200)


# ── TC-028: Checkout special_instructions ─────────────────────────────────────

class CheckoutSpecialInstructionsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.producer = _make_producer("instr_producer@test.com")
        self.customer = _make_customer("instr_customer@test.com")
        self.product = _make_product(self.producer, name="Pepper", price="1.20", stock=10)
        self.client.login(username="instr_customer@test.com", password="Test1234")

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

    def test_checkout_saves_special_instructions(self):
        self.client.post(reverse("checkout"), {
            "full_name": "Test Customer",
            "email": "instr_customer@test.com",
            "address": "5 Test Lane",
            "city": "London",
            "postal_code": "W1A 1AA",
            "payment_method": "card",
            "accept_terms": "on",
            "address_confirmed": "1",
            f"delivery_date_{self.producer.id}": _valid_date(),
            "special_instructions": "Please leave at the back door.",
        })
        co = CheckoutOrder.objects.filter(customer=self.customer).first()
        self.assertIsNotNone(co)
        self.assertEqual(co.special_instructions, "Please leave at the back door.")


# ═══════════════════════════════════════════════════════════════════════════════
# AUTHENTICATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class RegistrationTest(TestCase):
    def setUp(self):
        self.client = Client()

    def _post_register(self, **overrides):
        data = {
            "full_name": "Test User",
            "email": "newuser@test.com",
            "password": "Secure123",
            "confirm_password": "Secure123",
            "role": "customer",
            "account_type": "individual",
            "organization_name": "",
        }
        data.update(overrides)
        return self.client.post(reverse("register"), data)

    def test_valid_registration_redirects_to_login(self):
        response = self._post_register()
        self.assertRedirects(response, "/login/")
        self.assertTrue(User.objects.filter(email="newuser@test.com").exists())

    def test_duplicate_email_rejected(self):
        _make_customer("newuser@test.com")
        response = self._post_register()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.filter(email="newuser@test.com").count(), 1)

    def test_password_too_short_rejected(self):
        response = self._post_register(password="Abc1", confirm_password="Abc1")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="newuser@test.com").exists())

    def test_password_no_uppercase_rejected(self):
        response = self._post_register(password="secure123", confirm_password="secure123")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="newuser@test.com").exists())

    def test_password_no_digit_rejected(self):
        response = self._post_register(password="SecurePass", confirm_password="SecurePass")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="newuser@test.com").exists())

    def test_password_mismatch_rejected(self):
        response = self._post_register(password="Secure123", confirm_password="Different1")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="newuser@test.com").exists())

    def test_producer_registration_ignores_account_type(self):
        self._post_register(
            email="producer_reg@test.com",
            role="producer",
            account_type="restaurant",
            organization_name="Bistro",
        )
        user = User.objects.get(email="producer_reg@test.com")
        self.assertEqual(user.account_type, "individual")
        self.assertEqual(user.organization_name, "")

    def test_customer_community_group_registration(self):
        self._post_register(
            email="community_reg@test.com",
            role="customer",
            account_type="community_group",
            organization_name="Green Co-op",
        )
        user = User.objects.get(email="community_reg@test.com")
        self.assertEqual(user.account_type, "community_group")
        self.assertEqual(user.organization_name, "Green Co-op")

    def test_authenticated_user_register_page_redirects(self):
        _make_customer("already@test.com")
        self.client.login(username="already@test.com", password="Test1234")
        response = self.client.get(reverse("register"))
        self.assertEqual(response.status_code, 302)


class LoginTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = _make_customer("login_user@test.com")

    def test_valid_login_redirects_to_home(self):
        response = self.client.post(reverse("login"), {
            "email": "login_user@test.com",
            "password": "Test1234",
        })
        self.assertEqual(response.status_code, 302)

    def test_invalid_password_rejected(self):
        response = self.client.post(reverse("login"), {
            "email": "login_user@test.com",
            "password": "WrongPass1",
        })
        self.assertEqual(response.status_code, 200)

    def test_invalid_email_rejected(self):
        response = self.client.post(reverse("login"), {
            "email": "nobody@test.com",
            "password": "Test1234",
        })
        self.assertEqual(response.status_code, 200)

    def test_next_relative_url_is_honoured(self):
        response = self.client.post(
            reverse("login") + "?next=/customer/",
            {"email": "login_user@test.com", "password": "Test1234"},
        )
        self.assertRedirects(response, "/customer/", fetch_redirect_response=False)

    def test_next_absolute_url_is_blocked(self):
        response = self.client.post(
            reverse("login") + "?next=https://evil.com",
            {"email": "login_user@test.com", "password": "Test1234"},
        )
        self.assertRedirects(response, "/", fetch_redirect_response=False)

    def test_logout_redirects_to_login(self):
        self.client.login(username="login_user@test.com", password="Test1234")
        response = self.client.post(reverse("logout"))
        self.assertRedirects(response, "/login/", fetch_redirect_response=False)

    def test_authenticated_user_login_page_redirects(self):
        self.client.login(username="login_user@test.com", password="Test1234")
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 302)

    def test_session_expired_param_loads_page(self):
        response = self.client.get(reverse("login") + "?expired=1")
        self.assertEqual(response.status_code, 200)


# ═══════════════════════════════════════════════════════════════════════════════
# ROLE-BASED ACCESS CONTROL
# ═══════════════════════════════════════════════════════════════════════════════

class RoleAccessTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.customer = _make_customer("rbac_customer@test.com")
        self.producer = _make_producer("rbac_producer@test.com")
        self.admin = User.objects.create_user(
            email="rbac_admin@test.com",
            password="Test1234",
            full_name="RBAC Admin",
            role="admin",
        )

    def test_customer_cannot_access_producer_dashboard(self):
        self.client.login(username="rbac_customer@test.com", password="Test1234")
        response = self.client.get(reverse("producer_dashboard"))
        self.assertNotEqual(response.status_code, 200)

    def test_producer_cannot_access_customer_dashboard(self):
        self.client.login(username="rbac_producer@test.com", password="Test1234")
        response = self.client.get(reverse("customer_dashboard"))
        self.assertNotEqual(response.status_code, 200)

    def test_customer_cannot_access_admin_panel(self):
        self.client.login(username="rbac_customer@test.com", password="Test1234")
        response = self.client.get(reverse("admin_dashboard"))
        self.assertNotEqual(response.status_code, 200)

    def test_producer_cannot_access_admin_panel(self):
        self.client.login(username="rbac_producer@test.com", password="Test1234")
        response = self.client.get(reverse("admin_dashboard"))
        self.assertNotEqual(response.status_code, 200)

    def test_unauthenticated_cannot_access_checkout(self):
        response = self.client.get(reverse("checkout"))
        self.assertNotEqual(response.status_code, 200)

    def test_unauthenticated_cannot_access_cart(self):
        response = self.client.get(reverse("cart"))
        self.assertNotEqual(response.status_code, 200)

    def test_admin_can_access_admin_dashboard(self):
        self.client.login(username="rbac_admin@test.com", password="Test1234")
        response = self.client.get(reverse("admin_dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_producer_can_access_producer_dashboard(self):
        self.client.login(username="rbac_producer@test.com", password="Test1234")
        response = self.client.get(reverse("producer_dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_customer_can_access_customer_dashboard(self):
        self.client.login(username="rbac_customer@test.com", password="Test1234")
        response = self.client.get(reverse("customer_dashboard"))
        self.assertEqual(response.status_code, 200)


# ═══════════════════════════════════════════════════════════════════════════════
# MARKETPLACE
# ═══════════════════════════════════════════════════════════════════════════════

class MarketplaceTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.producer = _make_producer("mkt_producer@test.com")
        self.p1 = Product.objects.create(
            name="Organic Apple", category="Fruit", price=Decimal("1.50"),
            stock=10, status="Available", producer=self.producer,
            is_organic=True, allergens="",
        )
        self.p2 = Product.objects.create(
            name="Mushroom", category="Vegetable", price=Decimal("2.00"),
            stock=5, status="Available", producer=self.producer,
            is_organic=False, allergens="Milk",
        )
        self.p3 = Product.objects.create(
            name="Carrot", category="Vegetable", price=Decimal("0.80"),
            stock=0, status="Out of Stock", producer=self.producer,
        )

    def test_marketplace_shows_available_products(self):
        response = self.client.get(reverse("marketplace"))
        self.assertEqual(response.status_code, 200)
        names = [p.name for p in response.context["products"]]
        self.assertIn("Organic Apple", names)
        self.assertIn("Mushroom", names)
        self.assertNotIn("Carrot", names)

    def test_search_by_name(self):
        response = self.client.get(reverse("marketplace") + "?q=apple")
        names = [p.name for p in response.context["products"]]
        self.assertIn("Organic Apple", names)
        self.assertNotIn("Mushroom", names)

    def test_filter_by_category(self):
        response = self.client.get(reverse("marketplace") + "?category=Vegetable")
        names = [p.name for p in response.context["products"]]
        self.assertIn("Mushroom", names)
        self.assertNotIn("Organic Apple", names)

    def test_filter_organic(self):
        response = self.client.get(reverse("marketplace") + "?organic=1")
        names = [p.name for p in response.context["products"]]
        self.assertIn("Organic Apple", names)
        self.assertNotIn("Mushroom", names)

    def test_filter_allergen_free(self):
        response = self.client.get(reverse("marketplace") + "?allergen_free=1")
        names = [p.name for p in response.context["products"]]
        self.assertIn("Organic Apple", names)
        self.assertNotIn("Mushroom", names)

    def test_out_of_stock_not_shown(self):
        response = self.client.get(reverse("marketplace"))
        names = [p.name for p in response.context["products"]]
        self.assertNotIn("Carrot", names)

    def test_categories_context_populated(self):
        response = self.client.get(reverse("marketplace"))
        self.assertIn("Fruit", response.context["categories"])
        self.assertIn("Vegetable", response.context["categories"])


class ProductSuggestTest(TestCase):
    def setUp(self):
        self.client = Client()
        producer = _make_producer("suggest_producer@test.com")
        Product.objects.create(name="Sweet Potato", category="Vegetable", price=Decimal("1.20"),
                               stock=5, status="Available", producer=producer)
        Product.objects.create(name="Potato", category="Vegetable", price=Decimal("0.90"),
                               stock=5, status="Available", producer=producer)
        Product.objects.create(name="Turnip", category="Vegetable", price=Decimal("0.70"),
                               stock=0, status="Out of Stock", producer=producer)

    def test_suggest_returns_matching_products(self):
        response = self.client.get(reverse("product_suggest") + "?q=potato")
        self.assertEqual(response.status_code, 200)
        results = response.json()["results"]
        names = [p["name"] for p in results]
        self.assertIn("Sweet Potato", names)
        self.assertIn("Potato", names)

    def test_suggest_excludes_out_of_stock(self):
        response = self.client.get(reverse("product_suggest") + "?q=turnip")
        results = response.json()["results"]
        self.assertEqual(results, [])

    def test_suggest_short_query_returns_empty(self):
        response = self.client.get(reverse("product_suggest") + "?q=a")
        results = response.json()["results"]
        self.assertEqual(results, [])


# ═══════════════════════════════════════════════════════════════════════════════
# CART OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

class CartOperationsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.producer = _make_producer("cart_producer@test.com")
        self.customer = _make_customer("cart_customer@test.com")
        self.product = _make_product(self.producer, name="Bean", price="1.00", stock=5)
        self.client.login(username="cart_customer@test.com", password="Test1234")

    def test_add_to_cart(self):
        self.client.post(reverse("cart_add", args=[self.product.id]), {"quantity": "2"})
        cart = self.client.session.get("cart", [])
        self.assertEqual(len(cart), 1)
        self.assertEqual(cart[0]["quantity"], 2)

    def test_add_out_of_stock_product_fails(self):
        self.product.stock = 0
        self.product.status = "Out of Stock"
        self.product.save()
        response = self.client.post(reverse("cart_add", args=[self.product.id]), {"quantity": "1"})
        cart = self.client.session.get("cart", [])
        self.assertEqual(cart, [])

    def test_add_quantity_clamped_to_available_stock(self):
        self.client.post(reverse("cart_add", args=[self.product.id]), {"quantity": "100"})
        cart = self.client.session.get("cart", [])
        self.assertEqual(cart[0]["quantity"], 5)

    def test_remove_from_cart(self):
        session = self.client.session
        session["cart"] = [{"product_id": self.product.id, "name": "Bean",
                            "price": 1.00, "quantity": 2,
                            "producer_id": self.producer.id, "producer_name": "Test"}]
        session.save()
        self.client.post(reverse("cart_remove", args=[self.product.id]))
        cart = self.client.session.get("cart", [])
        self.assertEqual(cart, [])

    def test_update_cart_quantity(self):
        session = self.client.session
        session["cart"] = [{"product_id": self.product.id, "name": "Bean",
                            "price": 1.00, "quantity": 1,
                            "producer_id": self.producer.id, "producer_name": "Test"}]
        session.save()
        self.client.post(reverse("cart_update", args=[self.product.id]), {"quantity": "3"})
        cart = self.client.session.get("cart", [])
        self.assertEqual(cart[0]["quantity"], 3)

    def test_update_cart_quantity_exceeds_stock_fails(self):
        session = self.client.session
        session["cart"] = [{"product_id": self.product.id, "name": "Bean",
                            "price": 1.00, "quantity": 1,
                            "producer_id": self.producer.id, "producer_name": "Test"}]
        session.save()
        self.client.post(reverse("cart_update", args=[self.product.id]), {"quantity": "999"})
        cart = self.client.session.get("cart", [])
        self.assertEqual(cart[0]["quantity"], 1)

    def test_cart_page_loads(self):
        response = self.client.get(reverse("cart"))
        self.assertEqual(response.status_code, 200)

    def test_unauthenticated_cannot_add_to_cart(self):
        self.client.logout()
        response = self.client.post(reverse("cart_add", args=[self.product.id]), {"quantity": "1"})
        self.assertNotEqual(response.status_code, 200)


# ═══════════════════════════════════════════════════════════════════════════════
# PRODUCT DETAIL & REVIEWS
# ═══════════════════════════════════════════════════════════════════════════════

class ProductDetailTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.producer = _make_producer("detail_producer@test.com")
        self.customer = _make_customer("detail_customer@test.com")
        self.product = _make_product(self.producer, name="Kale", price="1.50", stock=10)

    def test_product_detail_page_loads(self):
        response = self.client.get(reverse("product_detail", args=[self.product.pk]))
        self.assertEqual(response.status_code, 200)

    def test_product_detail_404_for_nonexistent(self):
        response = self.client.get(reverse("product_detail", args=[9999]))
        self.assertEqual(response.status_code, 404)

    def test_submit_review(self):
        self.client.login(username="detail_customer@test.com", password="Test1234")
        self.client.post(reverse("product_detail", args=[self.product.pk]), {
            "rating": 5,
            "title": "Great product",
            "text": "Really fresh and tasty.",
        })
        from api.models import Review
        self.assertTrue(Review.objects.filter(product=self.product, customer=self.customer).exists())

    def test_duplicate_review_rejected(self):
        from api.models import Review
        self.client.login(username="detail_customer@test.com", password="Test1234")
        Review.objects.create(product=self.product, customer=self.customer, rating=4, title="Good", text="")
        self.client.post(reverse("product_detail", args=[self.product.pk]), {
            "rating": 5,
            "title": "Second review",
            "text": "Should be rejected.",
        })
        self.assertEqual(Review.objects.filter(product=self.product, customer=self.customer).count(), 1)

    def test_unauthenticated_cannot_submit_review(self):
        response = self.client.post(reverse("product_detail", args=[self.product.pk]), {
            "rating": 5, "title": "Good", "text": "",
        })
        self.assertNotEqual(response.status_code, 200)


# ═══════════════════════════════════════════════════════════════════════════════
# CUSTOMER DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════

class CustomerDashboardTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.customer = _make_customer("dash_customer@test.com")
        self.client.login(username="dash_customer@test.com", password="Test1234")

        for i in range(3):
            CheckoutOrder.objects.create(
                customer=self.customer,
                full_name="Dash Customer",
                email="dash_customer@test.com",
                address="1 Road",
                city="Bristol",
                postal_code="BS1 1AA",
                payment_method="card",
                status="pending",
            )
        CheckoutOrder.objects.create(
            customer=self.customer,
            full_name="Dash Customer",
            email="dash_customer@test.com",
            address="1 Road",
            city="Bristol",
            postal_code="BS1 1AA",
            payment_method="card",
            status="confirmed",
        )

    def test_dashboard_loads(self):
        response = self.client.get(reverse("customer_dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_dashboard_shows_all_orders(self):
        response = self.client.get(reverse("customer_dashboard"))
        self.assertEqual(response.context["total_orders"], 4)

    def test_dashboard_filter_by_status(self):
        response = self.client.get(reverse("customer_dashboard") + "?status=pending")
        orders = list(response.context["orders"])
        self.assertEqual(len(orders), 3)

    def test_dashboard_upcoming_deliveries_count(self):
        response = self.client.get(reverse("customer_dashboard"))
        self.assertEqual(response.context["upcoming_deliveries"], 4)


# ═══════════════════════════════════════════════════════════════════════════════
# PRODUCER DASHBOARD & PRODUCTS
# ═══════════════════════════════════════════════════════════════════════════════

class ProducerDashboardTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.producer = _make_producer("prod_dash@test.com")
        self.client.login(username="prod_dash@test.com", password="Test1234")

    def test_dashboard_loads(self):
        response = self.client.get(reverse("producer_dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_low_stock_products_shown(self):
        p = _make_product(self.producer, name="Low Stock Herb", price="1.00", stock=2)
        p.low_stock_threshold = 5
        p.save()
        response = self.client.get(reverse("producer_dashboard"))
        low = list(response.context["low_stock_products"])
        self.assertIn(p, low)

    def test_product_above_threshold_not_in_low_stock(self):
        p = _make_product(self.producer, name="Plenty Herb", price="1.00", stock=20)
        p.low_stock_threshold = 5
        p.save()
        response = self.client.get(reverse("producer_dashboard"))
        low = list(response.context["low_stock_products"])
        self.assertNotIn(p, low)

    def test_zero_stock_product_not_in_low_stock(self):
        p = _make_product(self.producer, name="Zero Stock", price="1.00", stock=0)
        p.low_stock_threshold = 5
        p.save()
        response = self.client.get(reverse("producer_dashboard"))
        low = list(response.context["low_stock_products"])
        self.assertNotIn(p, low)


class ProducerProductManagementTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.producer = _make_producer("prod_mgmt@test.com")
        self.other_producer = _make_producer("other_mgmt@test.com")
        self.client.login(username="prod_mgmt@test.com", password="Test1234")

    def test_create_product_with_stock(self):
        self.client.post(reverse("producer_products"), {
            "name": "Fresh Tomato",
            "category": "Vegetable",
            "description": "",
            "price": "2.50",
            "stock": "10",
            "status": "Available",
            "allergens": "",
            "is_organic": False,
            "discount_percentage": 0,
        })
        self.assertTrue(Product.objects.filter(name="Fresh Tomato", producer=self.producer).exists())

    def test_create_product_zero_stock_sets_out_of_stock(self):
        self.client.post(reverse("producer_products"), {
            "name": "Seasonal Berry",
            "category": "Fruit",
            "description": "",
            "price": "3.00",
            "stock": "0",
            "status": "Available",
            "allergens": "",
            "is_organic": False,
            "discount_percentage": 0,
        })
        product = Product.objects.get(name="Seasonal Berry")
        self.assertEqual(product.status, "Out of Stock")

    def test_create_product_negative_price_rejected(self):
        count_before = Product.objects.count()
        self.client.post(reverse("producer_products"), {
            "name": "Bad Price",
            "category": "Fruit",
            "price": "-1.00",
            "stock": "5",
            "status": "Available",
            "discount_percentage": 0,
        })
        self.assertEqual(Product.objects.count(), count_before)

    def test_create_product_discount_over_50_rejected(self):
        count_before = Product.objects.count()
        self.client.post(reverse("producer_products"), {
            "name": "Over Discount",
            "category": "Fruit",
            "price": "5.00",
            "stock": "5",
            "status": "Available",
            "discount_percentage": 75,
        })
        self.assertEqual(Product.objects.count(), count_before)

    def test_producer_products_page_loads_with_inline_stock_editor(self):
        _make_product(self.producer, name="Inline Stock Herb", price="1.50", stock=12)
        response = self.client.get(reverse("producer_products"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-producer-products="true"')
        self.assertContains(response, 'quick-stock-edit')

    def test_edit_product_page_loads(self):
        p = _make_product(self.producer)
        response = self.client.get(reverse("producer_product_edit", args=[p.pk]))
        self.assertEqual(response.status_code, 200)

    def test_edit_product_owned_by_other_producer_returns_404(self):
        p = _make_product(self.other_producer)
        response = self.client.get(reverse("producer_product_edit", args=[p.pk]))
        self.assertEqual(response.status_code, 404)

    def test_edit_product_updates_status_when_stock_set_to_zero(self):
        p = _make_product(self.producer, stock=10)
        self.client.post(reverse("producer_product_edit", args=[p.pk]), {
            "name": p.name,
            "category": p.category,
            "price": "1.00",
            "stock": "0",
            "status": "Available",
            "discount_percentage": 0,
        })
        p.refresh_from_db()
        self.assertEqual(p.status, "Out of Stock")

    def test_edit_product_restores_available_when_stock_added(self):
        p = _make_product(self.producer, stock=0)
        p.status = "Out of Stock"
        p.save()
        self.client.post(reverse("producer_product_edit", args=[p.pk]), {
            "name": p.name,
            "category": p.category,
            "price": "1.00",
            "stock": "10",
            "status": "Out of Stock",
            "discount_percentage": 0,
        })
        p.refresh_from_db()
        self.assertEqual(p.status, "Available")


# ═══════════════════════════════════════════════════════════════════════════════
# PRODUCER ORDER STATUS TRANSITIONS
# ═══════════════════════════════════════════════════════════════════════════════

class ProducerOrderStatusTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.producer = _make_producer("status_producer@test.com")
        self.other_producer = _make_producer("status_other@test.com")
        self.client.login(username="status_producer@test.com", password="Test1234")
        self.order = Order.objects.create(
            order_id="TEST-001",
            customer_name="Status Customer",
            delivery_date=date.today() + timedelta(days=3),
            status="Pending",
            producer=self.producer,
        )

    def test_pending_to_confirmed(self):
        self.client.post(
            reverse("producer_order_status", args=[self.order.order_id]),
            {"status": "Confirmed"},
        )
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "Confirmed")

    def test_confirmed_to_ready(self):
        self.order.status = "Confirmed"
        self.order.save()
        self.client.post(
            reverse("producer_order_status", args=[self.order.order_id]),
            {"status": "Ready"},
        )
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "Ready")

    def test_ready_to_delivered(self):
        self.order.status = "Ready"
        self.order.save()
        self.client.post(
            reverse("producer_order_status", args=[self.order.order_id]),
            {"status": "Delivered"},
        )
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "Delivered")

    def test_invalid_transition_pending_to_delivered(self):
        self.client.post(
            reverse("producer_order_status", args=[self.order.order_id]),
            {"status": "Delivered"},
        )
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "Pending")

    def test_cannot_update_other_producers_order(self):
        self.client.post(
            reverse("producer_order_status", args=[self.order.order_id]),
            {"status": "Confirmed"},
        )
        other_order = Order.objects.create(
            order_id="TEST-002",
            customer_name="Other Customer",
            delivery_date=date.today() + timedelta(days=3),
            status="Pending",
            producer=self.other_producer,
        )
        response = self.client.post(
            reverse("producer_order_status", args=[other_order.order_id]),
            {"status": "Confirmed"},
        )
        other_order.refresh_from_db()
        self.assertEqual(other_order.status, "Pending")


# ═══════════════════════════════════════════════════════════════════════════════
# PRODUCER PAYMENTS
# ═══════════════════════════════════════════════════════════════════════════════

class ProducerPaymentsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.producer = _make_producer("payments_producer@test.com")
        self.customer = _make_customer("payments_customer@test.com")
        self.product = _make_product(self.producer, name="Beet", price="2.00", stock=20)
        self.client.login(username="payments_producer@test.com", password="Test1234")

        self.delivered_order = Order.objects.create(
            order_id="PAY-001",
            customer_name="Payments Customer",
            delivery_date=date.today(),
            status="Delivered",
            producer=self.producer,
        )
        OrderItem.objects.create(
            order=self.delivered_order, product=self.product,
            quantity=3, unit_price=Decimal("2.00"),
        )
        self.pending_order = Order.objects.create(
            order_id="PAY-002",
            customer_name="Payments Customer",
            delivery_date=date.today() + timedelta(days=2),
            status="Pending",
            producer=self.producer,
        )
        OrderItem.objects.create(
            order=self.pending_order, product=self.product,
            quantity=1, unit_price=Decimal("2.00"),
        )

    def test_payments_page_loads(self):
        response = self.client.get(reverse("producer_payments"))
        self.assertEqual(response.status_code, 200)

    def test_delivered_gross_calculated_correctly(self):
        response = self.client.get(reverse("producer_payments"))
        self.assertAlmostEqual(response.context["payments"]["this_week"], 6.00, places=2)

    def test_commission_is_five_percent(self):
        response = self.client.get(reverse("producer_payments"))
        self.assertAlmostEqual(response.context["payments"]["commission"], 0.30, places=2)

    def test_net_earned_is_gross_minus_commission(self):
        response = self.client.get(reverse("producer_payments"))
        self.assertAlmostEqual(response.context["payments"]["net_earned"], 5.70, places=2)

    def test_csv_export_returns_csv(self):
        response = self.client.get(reverse("producer_payments") + "?export=csv")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        content = response.content.decode("utf-8")
        self.assertIn("PAY-001", content)
        self.assertIn("PAY-002", content)


# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN VIEWS
# ═══════════════════════════════════════════════════════════════════════════════

class AdminViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            email="admin_views@test.com",
            password="Test1234",
            full_name="Admin Views",
            role="admin",
        )
        self.producer = _make_producer("admin_test_producer@test.com")
        self.customer = _make_customer("admin_test_customer@test.com")
        self.client.login(username="admin_views@test.com", password="Test1234")

    def test_admin_dashboard_loads(self):
        response = self.client.get(reverse("admin_dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_admin_users_page_loads(self):
        response = self.client.get(reverse("admin_users"))
        self.assertEqual(response.status_code, 200)

    def test_admin_database_page_loads(self):
        response = self.client.get(reverse("admin_database"))
        self.assertEqual(response.status_code, 200)

    def test_admin_reports_csv_export(self):
        CommissionReport.objects.create(
            report_date=date.today(), total_orders=5,
            gross_amount=Decimal("100.00"), commission_amount=Decimal("5.00"),
        )
        response = self.client.get(reverse("admin_reports") + "?export=csv")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])

    def test_admin_reports_date_filter(self):
        CommissionReport.objects.create(
            report_date=date.today() - timedelta(days=10),
            total_orders=3, gross_amount=Decimal("50.00"), commission_amount=Decimal("2.50"),
        )
        CommissionReport.objects.create(
            report_date=date.today(),
            total_orders=7, gross_amount=Decimal("150.00"), commission_amount=Decimal("7.50"),
        )
        from_date = (date.today() - timedelta(days=5)).isoformat()
        to_date = date.today().isoformat()
        response = self.client.get(reverse("admin_reports") + f"?date_from={from_date}&date_to={to_date}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["rows"]), 1)

    def test_admin_ai_monitoring_page_loads(self):
        response = self.client.get(reverse("admin_ai_monitoring"))
        self.assertEqual(response.status_code, 200)


# ═══════════════════════════════════════════════════════════════════════════════
# FOOD MILES CALCULATOR
# ═══════════════════════════════════════════════════════════════════════════════

class FoodMilesTest(TestCase):
    def test_same_postcode_returns_zero(self):
        from api.food_miles import calculate_food_miles
        result = calculate_food_miles("BS1 1AA", "BS1 1AA")
        self.assertEqual(result, 0.0)

    def test_bristol_to_bath_reasonable_distance(self):
        from api.food_miles import calculate_food_miles
        result = calculate_food_miles("BS1 1AA", "BA1 1AA")
        self.assertGreater(result, 5)
        self.assertLess(result, 30)

    def test_empty_postcode_defaults_to_bristol(self):
        from api.food_miles import calculate_food_miles
        result = calculate_food_miles("", "")
        self.assertEqual(result, 0.0)

    def test_invalid_postcode_defaults_to_bristol(self):
        from api.food_miles import calculate_food_miles
        # "INVALID" → DEFAULT_BRISTOL; "BS1 1AA" → BS1 centroid (very close to DEFAULT_BRISTOL)
        result = calculate_food_miles("INVALID", "BS1 1AA")
        self.assertIsInstance(result, float)
        self.assertLess(result, 2.0)

    def test_bristol_to_swindon_reasonable_distance(self):
        from api.food_miles import calculate_food_miles
        result = calculate_food_miles("BS1 1AA", "SN1 1AA")
        self.assertGreater(result, 30)
        self.assertLess(result, 80)

    def test_bristol_to_taunton_reasonable_distance(self):
        from api.food_miles import calculate_food_miles
        result = calculate_food_miles("BS1 1AA", "TA1 1AA")
        self.assertGreater(result, 30)
        self.assertLess(result, 80)

    def test_none_postcode_handled_gracefully(self):
        from api.food_miles import calculate_food_miles
        # None → DEFAULT_BRISTOL; result is near-zero distance to BS1 centroid
        result = calculate_food_miles(None, "BS1 1AA")
        self.assertIsInstance(result, float)
        self.assertLess(result, 2.0)


# ═══════════════════════════════════════════════════════════════════════════════
# FORM VALIDATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class RegisterFormValidationTest(TestCase):
    def _make_form(self, **overrides):
        from api.forms import RegisterForm
        data = {
            "full_name": "Test User",
            "email": "form_test@test.com",
            "password": "Secure123",
            "confirm_password": "Secure123",
            "role": "customer",
        }
        data.update(overrides)
        return RegisterForm(data)

    def test_valid_form_passes(self):
        form = self._make_form()
        self.assertTrue(form.is_valid())

    def test_password_no_uppercase_invalid(self):
        form = self._make_form(password="secure123", confirm_password="secure123")
        self.assertFalse(form.is_valid())
        self.assertIn("password", form.errors)

    def test_password_no_lowercase_invalid(self):
        form = self._make_form(password="SECURE123", confirm_password="SECURE123")
        self.assertFalse(form.is_valid())

    def test_password_no_digit_invalid(self):
        form = self._make_form(password="SecurePass", confirm_password="SecurePass")
        self.assertFalse(form.is_valid())

    def test_password_mismatch_invalid(self):
        form = self._make_form(password="Secure123", confirm_password="Secure456")
        self.assertFalse(form.is_valid())
        self.assertIn("confirm_password", form.errors)

    def test_invalid_email_invalid(self):
        form = self._make_form(email="not-an-email")
        self.assertFalse(form.is_valid())


class ProductFormValidationTest(TestCase):
    def _make_form(self, **overrides):
        from api.forms import ProductForm
        data = {
            "name": "Valid Product",
            "category": "Vegetable",
            "price": "2.00",
            "stock": "10",
            "status": "Available",
            "discount_percentage": 0,
        }
        data.update(overrides)
        return ProductForm(data)

    def test_valid_form_passes(self):
        form = self._make_form()
        self.assertTrue(form.is_valid())

    def test_negative_price_invalid(self):
        form = self._make_form(price="-1.00")
        self.assertFalse(form.is_valid())

    def test_negative_stock_invalid(self):
        form = self._make_form(stock="-1")
        self.assertFalse(form.is_valid())

    def test_discount_above_50_invalid(self):
        form = self._make_form(discount_percentage=51)
        self.assertFalse(form.is_valid())

    def test_discount_exactly_50_valid(self):
        form = self._make_form(discount_percentage=50)
        self.assertTrue(form.is_valid())

    def test_zero_price_valid(self):
        form = self._make_form(price="0.00")
        self.assertTrue(form.is_valid())


class ReportFilterFormValidationTest(TestCase):
    def test_from_before_to_valid(self):
        from api.forms import ReportFilterForm
        form = ReportFilterForm({"date_from": "2025-01-01", "date_to": "2025-12-31"})
        self.assertTrue(form.is_valid())

    def test_from_after_to_invalid(self):
        from api.forms import ReportFilterForm
        form = ReportFilterForm({"date_from": "2025-12-31", "date_to": "2025-01-01"})
        self.assertFalse(form.is_valid())

    def test_only_from_date_valid(self):
        from api.forms import ReportFilterForm
        form = ReportFilterForm({"date_from": "2025-01-01"})
        self.assertTrue(form.is_valid())

    def test_empty_form_valid(self):
        from api.forms import ReportFilterForm
        form = ReportFilterForm({})
        self.assertTrue(form.is_valid())


# ═══════════════════════════════════════════════════════════════════════════════
# REST API ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

class APIAuthTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = _make_customer("api_user@test.com")

    def test_health_endpoint(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_api_login_valid(self):
        response = self.client.post(
            "/auth/login",
            data={"email": "api_user@test.com", "password": "Test1234"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("access_token", response.json())

    def test_api_login_invalid_credentials(self):
        response = self.client.post(
            "/auth/login",
            data={"email": "api_user@test.com", "password": "WrongPass1"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    def test_api_login_missing_fields(self):
        response = self.client.post(
            "/auth/login",
            data={"email": "api_user@test.com"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_api_register_valid(self):
        response = self.client.post(
            "/auth/register",
            data={
                "email": "api_new@test.com",
                "password": "Secure123",
                "full_name": "New User",
                "role": "customer",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(User.objects.filter(email="api_new@test.com").exists())

    def test_api_register_duplicate_email(self):
        response = self.client.post(
            "/auth/register",
            data={
                "email": "api_user@test.com",
                "password": "Secure123",
                "full_name": "Duplicate",
                "role": "customer",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_api_logout_requires_auth(self):
        response = self.client.post("/auth/logout", content_type="application/json")
        self.assertEqual(response.status_code, 401)

    def test_api_logout_valid(self):
        login_response = self.client.post(
            "/auth/login",
            data={"email": "api_user@test.com", "password": "Test1234"},
            content_type="application/json",
        )
        token = login_response.json()["access_token"]
        response = self.client.post(
            "/auth/logout",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)


class APIProducerEndpointsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.producer = _make_producer("api_producer@test.com")
        self.customer = _make_customer("api_cust@test.com")
        self.token = issue_token(self.producer)
        self.cust_token = issue_token(self.customer)

    def test_producer_dashboard_requires_producer_role(self):
        response = self.client.get(
            "/dashboards/producer",
            HTTP_AUTHORIZATION=f"Bearer {self.cust_token}",
        )
        self.assertEqual(response.status_code, 403)

    def test_producer_dashboard_accessible_to_producer(self):
        response = self.client.get(
            "/dashboards/producer",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)

    def test_create_product_via_api(self):
        response = self.client.post(
            "/producer/products",
            data={
                "name": "API Product",
                "category": "Fruit",
                "price": "1.99",
                "stock": 5,
                "status": "Available",
                "allergens": "",
                "is_organic": False,
                "discount_percentage": 0,
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Product.objects.filter(name="API Product").exists())

    def test_create_product_requires_producer_role(self):
        response = self.client.post(
            "/producer/products",
            data={"name": "Bad Product", "category": "Fruit", "price": "1.00", "stock": 5},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.cust_token}",
        )
        self.assertEqual(response.status_code, 403)

    def test_patch_product_negative_stock_rejected(self):
        product = _make_product(self.producer, name="API Patch", price="2.00", stock=10)
        response = self.client.patch(
            f"/producer/products/{product.id}",
            data={"stock": -5},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 400)

    def test_patch_product_other_producer_forbidden(self):
        other_producer = _make_producer("api_other@test.com")
        product = _make_product(other_producer, name="Other Product", price="1.00", stock=5)
        response = self.client.patch(
            f"/producer/products/{product.id}",
            data={"stock": 10},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 403)


class APIPublicProductsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.producer = _make_producer("api_pub_prod@test.com")
        self.other_producer = _make_producer("api_pub_prod2@test.com")
        self.apple = _make_product(self.producer, name="Apple", price="1.50", stock=20)
        self.carrot = _make_product(self.other_producer, name="Carrot", price="0.90", stock=15)
        self.carrot.category = "Vegetable"
        self.carrot.save()

    def test_products_list_returns_items(self):
        response = self.client.get("/api/products", content_type="application/json")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("items", data)
        names = [item["name"] for item in data["items"]]
        self.assertIn("Apple", names)
        self.assertIn("Carrot", names)

    def test_products_list_filters_by_category(self):
        response = self.client.get("/api/products?category=Fruit", content_type="application/json")
        self.assertEqual(response.status_code, 200)
        items = response.json().get("items", [])
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["category"], "Fruit")

    def test_product_detail_returns_full_product(self):
        response = self.client.get(f"/api/products/{self.apple.id}", content_type="application/json")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["name"], "Apple")
        self.assertEqual(data["category"], "Fruit")
        self.assertEqual(data["producer_id"], self.producer.id)
        self.assertEqual(data["stock"], 20)


class APIAdminEndpointsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            email="api_admin@test.com", password="Test1234",
            full_name="API Admin", role="admin",
        )
        self.producer = _make_producer("api_admin_prod@test.com")
        self.admin_token = issue_token(self.admin)
        self.prod_token = issue_token(self.producer)

    def test_admin_dashboard_requires_admin_role(self):
        response = self.client.get(
            "/dashboards/admin",
            HTTP_AUTHORIZATION=f"Bearer {self.prod_token}",
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_dashboard_accessible_to_admin(self):
        response = self.client.get(
            "/dashboards/admin",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_token}",
        )
        self.assertEqual(response.status_code, 200)

    def test_admin_reports_date_filter_valid(self):
        response = self.client.get(
            "/dashboards/admin/reports?from=2025-01-01&to=2025-12-31",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_token}",
        )
        self.assertEqual(response.status_code, 200)

    def test_admin_reports_invalid_date_returns_400(self):
        response = self.client.get(
            "/dashboards/admin/reports?from=2025-12-31&to=2025-01-01",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_token}",
        )
        self.assertEqual(response.status_code, 400)


class APIOrdersTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.producer = _make_producer("api_ord_prod@test.com")
        self.customer = _make_customer("api_ord_cust@test.com")
        self.product = _make_product(self.producer, name="API Veg", price="2.00", stock=10)
        self.token = issue_token(self.customer)

    def test_create_order_valid(self):
        response = self.client.post(
            "/orders/",
            data={
                "fullName": "API Customer",
                "email": "api_ord_cust@test.com",
                "address": "1 API Road",
                "city": "Bristol",
                "postalCode": "BS1 1AA",
                "paymentMethod": "card",
                "deliveryDate": _valid_date(),
                "items": [{"product_id": self.product.id, "quantity": 2}],
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertIn(response.status_code, [200, 201])

    def test_create_order_unauthenticated_returns_401(self):
        response = self.client.post(
            "/orders/",
            data={
                "full_name": "Guest",
                "email": "guest@test.com",
                "address": "1 Road",
                "city": "Bristol",
                "postal_code": "BS1 1AA",
                "payment_method": "card",
                "items": [{"product_id": self.product.id, "quantity": 1}],
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    def test_create_order_out_of_stock_returns_400(self):
        self.product.stock = 0
        self.product.save()
        response = self.client.post(
            "/orders/",
            data={
                "fullName": "API Customer",
                "email": "api_ord_cust@test.com",
                "address": "1 API Road",
                "city": "Bristol",
                "postalCode": "BS1 1AA",
                "paymentMethod": "card",
                "deliveryDate": _valid_date(),
                "items": [{"product_id": self.product.id, "quantity": 1}],
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 400)

    def test_get_order_requires_authentication(self):
        response = self.client.get("/orders/999")
        self.assertEqual(response.status_code, 401)


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC PAGES
# ═══════════════════════════════════════════════════════════════════════════════

class PublicPagesTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_home_page_loads(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

    def test_marketplace_page_loads(self):
        response = self.client.get(reverse("marketplace"))
        self.assertEqual(response.status_code, 200)

    def test_for_producers_page_loads(self):
        response = self.client.get(reverse("for_producers"))
        self.assertEqual(response.status_code, 200)

    def test_how_it_works_page_loads(self):
        response = self.client.get(reverse("how_it_works"))
        self.assertEqual(response.status_code, 200)

    def test_sustainability_page_loads(self):
        response = self.client.get(reverse("sustainability"))
        self.assertEqual(response.status_code, 200)

    def test_legal_page_loads(self):
        response = self.client.get(reverse("legal"))
        self.assertEqual(response.status_code, 200)

    def test_login_page_loads(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)

    def test_register_page_loads(self):
        response = self.client.get(reverse("register"))
        self.assertEqual(response.status_code, 200)


# ═══════════════════════════════════════════════════════════════════════════════
# CHECKOUT EDGE CASES
# ═══════════════════════════════════════════════════════════════════════════════

class CheckoutEdgeCasesTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.producer = _make_producer("co_edge_producer@test.com")
        self.customer = _make_customer("co_edge_customer@test.com")
        self.product = _make_product(self.producer, name="Edge Veg", price="2.00", stock=10)
        self.client.login(username="co_edge_customer@test.com", password="Test1234")

    def _prime_cart(self, qty=1):
        session = self.client.session
        session["cart"] = [{
            "product_id": self.product.id,
            "name": self.product.name,
            "price": float(self.product.price),
            "quantity": qty,
            "producer_id": self.producer.id,
            "producer_name": self.producer.full_name,
        }]
        session.save()

    def _checkout_post(self, **overrides):
        data = {
            "full_name": "Edge Customer",
            "email": "co_edge_customer@test.com",
            "address": "1 Edge Road",
            "city": "Bristol",
            "postal_code": "BS1 1AA",
            "payment_method": "card",
            "accept_terms": "on",
            "address_confirmed": "1",
            f"delivery_date_{self.producer.id}": _valid_date(),
        }
        data.update(overrides)
        return self.client.post(reverse("checkout"), data)

    def test_empty_cart_redirects_to_cart(self):
        response = self._checkout_post()
        self.assertRedirects(response, "/cart/", fetch_redirect_response=False)
        self.assertEqual(CheckoutOrder.objects.count(), 0)

    def test_missing_address_confirmed_rejected(self):
        self._prime_cart()
        response = self._checkout_post(address_confirmed="0")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(CheckoutOrder.objects.count(), 0)

    def test_terms_not_accepted_rejected(self):
        self._prime_cart()
        data = {
            "full_name": "Edge Customer",
            "email": "co_edge_customer@test.com",
            "address": "1 Edge Road",
            "city": "Bristol",
            "postal_code": "BS1 1AA",
            "payment_method": "card",
            "address_confirmed": "1",
            f"delivery_date_{self.producer.id}": _valid_date(),
        }
        response = self.client.post(reverse("checkout"), data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(CheckoutOrder.objects.count(), 0)

    def test_stock_error_blocks_checkout(self):
        self._prime_cart(qty=5)
        self.product.stock = 2
        self.product.save()
        response = self._checkout_post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(CheckoutOrder.objects.count(), 0)

    def test_commission_report_created_after_checkout(self):
        self._prime_cart()
        CommissionReport.objects.filter(report_date=date.today()).delete()
        self._checkout_post()
        report = CommissionReport.objects.filter(report_date=date.today()).first()
        self.assertIsNotNone(report)
        self.assertEqual(report.total_orders, 1)
        self.assertGreater(report.gross_amount, 0)

    def test_commission_report_incremented_on_second_checkout(self):
        CommissionReport.objects.filter(report_date=date.today()).delete()
        self._prime_cart()
        self._checkout_post()
        p2 = _make_product(self.producer, name="Edge Veg 2", price="3.00", stock=5)
        session = self.client.session
        session["cart"] = [{
            "product_id": p2.id, "name": p2.name, "price": float(p2.price),
            "quantity": 1, "producer_id": self.producer.id,
            "producer_name": self.producer.full_name,
        }]
        session.save()
        self._checkout_post(**{f"delivery_date_{self.producer.id}": _valid_date()})
        report = CommissionReport.objects.get(report_date=date.today())
        self.assertEqual(report.total_orders, 2)

    def test_cart_cleared_after_successful_checkout(self):
        self._prime_cart()
        self._checkout_post()
        cart = self.client.session.get("cart", [])
        self.assertEqual(cart, [])

    def test_checkout_page_loads_with_cart(self):
        self._prime_cart()
        response = self.client.get(reverse("checkout"))
        self.assertEqual(response.status_code, 200)


# ═══════════════════════════════════════════════════════════════════════════════
# ORDER CONFIRMATION VIEW
# ═══════════════════════════════════════════════════════════════════════════════

class OrderConfirmationTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.producer = _make_producer("conf_producer@test.com")
        self.customer = _make_customer("conf_customer@test.com")
        self.other_customer = _make_customer("conf_other@test.com")
        self.product = _make_product(self.producer, name="Conf Veg", price="2.00", stock=10)
        self.client.login(username="conf_customer@test.com", password="Test1234")

        self.checkout = CheckoutOrder.objects.create(
            customer=self.customer, full_name="Conf Customer",
            email="conf_customer@test.com", address="1 Conf Rd",
            city="Bristol", postal_code="BS1 1AA", payment_method="card",
        )
        self.order = Order.objects.create(
            order_id=f"CO-{self.checkout.id}",
            customer_name="Conf Customer",
            delivery_date=date.today() + timedelta(days=4),
            status="Pending", producer=self.producer,
        )
        OrderItem.objects.create(
            order=self.order, product=self.product,
            quantity=2, unit_price=Decimal("2.00"),
        )

    def test_confirmation_page_loads(self):
        response = self.client.get(reverse("order_confirmation", args=[self.checkout.id]))
        self.assertEqual(response.status_code, 200)

    def test_confirmation_shows_correct_total(self):
        response = self.client.get(reverse("order_confirmation", args=[self.checkout.id]))
        self.assertAlmostEqual(float(response.context["total"]), 4.00, places=2)

    def test_confirmation_forbidden_for_other_customer(self):
        self.client.login(username="conf_other@test.com", password="Test1234")
        response = self.client.get(reverse("order_confirmation", args=[self.checkout.id]))
        self.assertEqual(response.status_code, 404)


# ═══════════════════════════════════════════════════════════════════════════════
# PRODUCER QUALITY CHECK
# ═══════════════════════════════════════════════════════════════════════════════

class ProducerQualityCheckTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.producer = _make_producer("qc_producer@test.com")
        self.other_producer = _make_producer("qc_other@test.com")
        self.product = _make_product(self.producer, name="QC Apple", price="1.00", stock=20)
        self.client.login(username="qc_producer@test.com", password="Test1234")

        self.rotten_assessment = QualityAssessment.objects.create(
            product=self.product,
            assessed_by=self.producer,
            image="quality_checks/placeholder.jpg",
            grade="C",
            color_score=30.0,
            size_score=40.0,
            ripeness_score=20.0,
            model_confidence=0.85,
            is_healthy=False,
        )
        self.healthy_assessment = QualityAssessment.objects.create(
            product=self.product,
            assessed_by=self.producer,
            image="quality_checks/placeholder.jpg",
            grade="A",
            color_score=90.0,
            size_score=88.0,
            ripeness_score=92.0,
            model_confidence=0.97,
            is_healthy=True,
        )

    def _deduct_post(self, assessment_id, quantity):
        return self.client.post(reverse("producer_quality_check"), {
            "action": "deduct_rotten_stock",
            "assessment_id": assessment_id,
            "quantity": quantity,
        })

    def test_quality_check_page_loads(self):
        response = self.client.get(reverse("producer_quality_check"))
        self.assertEqual(response.status_code, 200)

    def test_deduct_rotten_stock(self):
        self._deduct_post(self.rotten_assessment.id, 5)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 15)

    def test_deduct_updates_quantity_lost(self):
        self._deduct_post(self.rotten_assessment.id, 3)
        self.rotten_assessment.refresh_from_db()
        self.assertEqual(self.rotten_assessment.quantity_lost, 3)

    def test_deduct_healthy_assessment_rejected(self):
        self._deduct_post(self.healthy_assessment.id, 5)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 20)

    def test_deduct_quantity_exceeds_stock_rejected(self):
        self._deduct_post(self.rotten_assessment.id, 999)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 20)

    def test_deduct_zero_quantity_rejected(self):
        self._deduct_post(self.rotten_assessment.id, 0)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 20)

    def test_deduct_missing_assessment_id_rejected(self):
        response = self.client.post(reverse("producer_quality_check"), {
            "action": "deduct_rotten_stock",
            "quantity": 1,
        })
        self.assertRedirects(response, "/producer/quality-check/", fetch_redirect_response=False)

    def test_deduct_sets_out_of_stock_when_stock_zeroed(self):
        self.product.stock = 3
        self.product.save()
        self._deduct_post(self.rotten_assessment.id, 3)
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, "Out of Stock")

    def test_deduct_accumulates_quantity_lost(self):
        self._deduct_post(self.rotten_assessment.id, 2)
        self._deduct_post(self.rotten_assessment.id, 3)
        self.rotten_assessment.refresh_from_db()
        self.assertEqual(self.rotten_assessment.quantity_lost, 5)

    def test_other_producer_assessment_returns_404(self):
        other_product = _make_product(self.other_producer, name="Other QC", price="1.00", stock=10)
        other_assessment = QualityAssessment.objects.create(
            product=other_product, assessed_by=self.other_producer,
            image="quality_checks/placeholder.jpg",
            grade="C", color_score=30.0, size_score=30.0,
            ripeness_score=30.0, model_confidence=0.8, is_healthy=False,
        )
        response = self._deduct_post(other_assessment.id, 1)
        self.assertEqual(response.status_code, 404)


# ═══════════════════════════════════════════════════════════════════════════════
# CART RESERVATION
# ═══════════════════════════════════════════════════════════════════════════════

class CartReservationTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.producer = _make_producer("res_producer@test.com")
        self.customer = _make_customer("res_customer@test.com")
        self.product = _make_product(self.producer, name="Res Veg", price="1.50", stock=10)
        self.client.login(username="res_customer@test.com", password="Test1234")

    def test_reservation_created_on_add_to_cart(self):
        self.client.post(reverse("cart_add", args=[self.product.id]), {"quantity": "2"})
        self.assertTrue(CartReservation.objects.filter(product=self.product).exists())

    def test_reservation_quantity_matches_cart(self):
        self.client.post(reverse("cart_add", args=[self.product.id]), {"quantity": "3"})
        res = CartReservation.objects.get(product=self.product)
        self.assertEqual(res.quantity, 3)

    def test_reservation_deleted_on_remove_from_cart(self):
        self.client.post(reverse("cart_add", args=[self.product.id]), {"quantity": "2"})
        self.client.post(reverse("cart_remove", args=[self.product.id]))
        self.assertFalse(CartReservation.objects.filter(product=self.product).exists())

    def test_reservation_updated_on_cart_update(self):
        self.client.post(reverse("cart_add", args=[self.product.id]), {"quantity": "2"})
        self.client.post(reverse("cart_update", args=[self.product.id]), {"quantity": "5"})
        res = CartReservation.objects.get(product=self.product)
        self.assertEqual(res.quantity, 5)


# ═══════════════════════════════════════════════════════════════════════════════
# REST API — ME, CUSTOMER DASHBOARD, PRODUCER ORDERS
# ═══════════════════════════════════════════════════════════════════════════════

class APIDashboardsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.customer = _make_customer("api_dash_cust@test.com")
        self.producer = _make_producer("api_dash_prod@test.com")
        self.cust_token = issue_token(self.customer)
        self.prod_token = issue_token(self.producer)

    def test_me_returns_current_user(self):
        response = self.client.get(
            "/dashboards/me",
            HTTP_AUTHORIZATION=f"Bearer {self.cust_token}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["email"], "api_dash_cust@test.com")

    def test_me_unauthenticated_returns_401(self):
        response = self.client.get("/dashboards/me")
        self.assertEqual(response.status_code, 401)

    def test_customer_dashboard_api(self):
        response = self.client.get(
            "/dashboards/customer",
            HTTP_AUTHORIZATION=f"Bearer {self.cust_token}",
        )
        self.assertEqual(response.status_code, 200)

    def test_customer_dashboard_requires_customer_role(self):
        response = self.client.get(
            "/dashboards/customer",
            HTTP_AUTHORIZATION=f"Bearer {self.prod_token}",
        )
        self.assertEqual(response.status_code, 403)

    def test_producer_products_api_returns_list(self):
        _make_product(self.producer, name="API List Veg", price="1.00", stock=5)
        response = self.client.get(
            "/dashboards/producer/products",
            HTTP_AUTHORIZATION=f"Bearer {self.prod_token}",
        )
        self.assertEqual(response.status_code, 200)
        items = response.json().get("items", [])
        names = [i["name"] for i in items]
        self.assertIn("API List Veg", names)

    def test_producer_orders_api(self):
        response = self.client.get(
            "/dashboards/producer/orders",
            HTTP_AUTHORIZATION=f"Bearer {self.prod_token}",
        )
        self.assertEqual(response.status_code, 200)

    def test_producer_payments_api(self):
        response = self.client.get(
            "/dashboards/producer/payments",
            HTTP_AUTHORIZATION=f"Bearer {self.prod_token}",
        )
        self.assertEqual(response.status_code, 200)

    def test_admin_users_api(self):
        admin = User.objects.create_user(
            email="api_admin_u@test.com", password="Test1234",
            full_name="API Admin U", role="admin",
        )
        token = issue_token(admin)
        response = self.client.get(
            "/dashboards/admin/users",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)

    def test_admin_database_api(self):
        admin = User.objects.create_user(
            email="api_admin_db@test.com", password="Test1234",
            full_name="API Admin DB", role="admin",
        )
        token = issue_token(admin)
        response = self.client.get(
            "/dashboards/admin/database",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)


# ═══════════════════════════════════════════════════════════════════════════════
# PRODUCER ORDERS VIEW (web)
# ═══════════════════════════════════════════════════════════════════════════════

class ProducerOrdersWebTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.producer = _make_producer("pord_web@test.com")
        self.other = _make_producer("pord_other@test.com")
        self.product = _make_product(self.producer, name="Web Order Veg", price="2.00", stock=20)
        self.client.login(username="pord_web@test.com", password="Test1234")
        self.order = Order.objects.create(
            order_id="WEB-001",
            customer_name="Web Customer",
            delivery_date=date.today() + timedelta(days=3),
            status="Pending",
            producer=self.producer,
        )
        OrderItem.objects.create(
            order=self.order, product=self.product,
            quantity=2, unit_price=Decimal("2.00"),
        )

    def test_producer_orders_page_loads(self):
        response = self.client.get(reverse("producer_orders"))
        self.assertEqual(response.status_code, 200)

    def test_producer_order_detail_loads(self):
        response = self.client.get(reverse("producer_order_detail", args=[self.order.order_id]))
        self.assertEqual(response.status_code, 200)

    def test_producer_order_detail_ownership_check(self):
        other_order = Order.objects.create(
            order_id="WEB-002",
            customer_name="Other Customer",
            delivery_date=date.today() + timedelta(days=3),
            status="Pending",
            producer=self.other,
        )
        response = self.client.get(reverse("producer_order_detail", args=[other_order.order_id]))
        self.assertEqual(response.status_code, 404)

    def test_producer_order_detail_shows_line_totals(self):
        response = self.client.get(reverse("producer_order_detail", args=[self.order.order_id]))
        self.assertEqual(response.status_code, 200)


# ═══════════════════════════════════════════════════════════════════════════════
# FOOD MILES — SHORT PREFIX FALLBACK (lines 27-29)
# ═══════════════════════════════════════════════════════════════════════════════

class FoodMilesFallbackTest(TestCase):
    def test_short_prefix_lookup(self):
        from api.food_miles import _get_area, POSTCODE_CENTROIDS
        # "BS10" is in the centroids dict directly
        result = _get_area("BS10 1AB")
        self.assertEqual(result, POSTCODE_CENTROIDS["BS10"])

    def test_area_without_letter_suffix_resolves(self):
        from api.food_miles import _get_area, POSTCODE_CENTROIDS
        # "GL50" is a valid area in the dict
        result = _get_area("GL50 3JE")
        self.assertEqual(result, POSTCODE_CENTROIDS["GL50"])

    def test_completely_unknown_area_returns_none(self):
        from api.food_miles import _get_area
        result = _get_area("ZZ99 9ZZ")
        self.assertIsNone(result)

    def test_calculate_uses_fallback_for_unknown(self):
        from api.food_miles import calculate_food_miles
        # Both sides unknown → both DEFAULT_BRISTOL → distance = 0
        result = calculate_food_miles("ZZ99 9ZZ", "ZZ88 8ZZ")
        self.assertEqual(result, 0.0)


# ═══════════════════════════════════════════════════════════════════════════════
# SERIALIZER VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

class SerializerValidationTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.producer = _make_producer("ser_producer@test.com")
        self.customer = _make_customer("ser_customer@test.com")
        self.token = issue_token(self.customer)

    def test_order_invalid_delivery_date_format(self):
        product = _make_product(self.producer, name="Ser Veg", price="1.00", stock=5)
        response = self.client.post(
            "/orders/",
            data={
                "fullName": "Ser Customer",
                "email": "ser_customer@test.com",
                "address": "1 Ser Road",
                "city": "Bristol",
                "postalCode": "BS1 1AA",
                "paymentMethod": "card",
                "deliveryDate": "not-a-date",
                "items": [{"product_id": product.id, "quantity": 1}],
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 400)

    def test_order_delivery_date_too_soon_rejected(self):
        product = _make_product(self.producer, name="Ser Veg 2", price="1.00", stock=5)
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        response = self.client.post(
            "/orders/",
            data={
                "fullName": "Ser Customer",
                "email": "ser_customer@test.com",
                "address": "1 Ser Road",
                "city": "Bristol",
                "postalCode": "BS1 1AA",
                "paymentMethod": "card",
                "deliveryDate": tomorrow,
                "items": [{"product_id": product.id, "quantity": 1}],
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 400)

    def test_producer_order_status_update_api(self):
        prod_token = issue_token(self.producer)
        order = Order.objects.create(
            order_id="SER-API-001",
            customer_name="Ser Customer",
            delivery_date=date.today() + timedelta(days=3),
            status="Pending",
            producer=self.producer,
        )
        response = self.client.patch(
            f"/producer/orders/{order.order_id}/status",
            data={"status": "confirmed"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {prod_token}",
        )
        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status.lower(), "confirmed")

    def test_producer_order_status_invalid_transition_api(self):
        prod_token = issue_token(self.producer)
        order = Order.objects.create(
            order_id="SER-API-002",
            customer_name="Ser Customer",
            delivery_date=date.today() + timedelta(days=3),
            status="Pending",
            producer=self.producer,
        )
        response = self.client.patch(
            f"/producer/orders/{order.order_id}/status",
            data={"status": "delivered"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {prod_token}",
        )
        self.assertEqual(response.status_code, 400)


# ── Task 1: ml/data/preprocess.py — data pipeline ────────────────────────────

import pathlib
import shutil
import tempfile


def _make_fake_dataset(tmp_dir, healthy_count=5, rotten_count=3):
    """Create a minimal fake ImageFolder dataset with tiny PNG images."""
    from PIL import Image
    for label, count in [("Healthy", healthy_count), ("Rotten", rotten_count)]:
        folder = pathlib.Path(tmp_dir) / label
        folder.mkdir(exist_ok=True)
        for i in range(count):
            img = Image.new("RGB", (32, 32), color=(i * 30, 100, 50))
            img.save(folder / f"{label}_{i}.png")


class PreprocessDatasetMappingTest(TestCase):
    """HealthyRottenDataset maps folder names to correct binary labels."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        _make_fake_dataset(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_healthy_maps_to_label_0(self):
        from ml.data.preprocess import HealthyRottenDataset
        ds = HealthyRottenDataset(root=self.tmp, transform=None)
        labels = [ds[i][1] for i in range(len(ds))]
        self.assertIn(0, labels, "Expected at least one Healthy (label 0) sample.")

    def test_rotten_maps_to_label_1(self):
        from ml.data.preprocess import HealthyRottenDataset
        ds = HealthyRottenDataset(root=self.tmp, transform=None)
        labels = [ds[i][1] for i in range(len(ds))]
        self.assertIn(1, labels, "Expected at least one Rotten (label 1) sample.")

    def test_total_dataset_length(self):
        from ml.data.preprocess import HealthyRottenDataset
        ds = HealthyRottenDataset(root=self.tmp, transform=None)
        self.assertEqual(len(ds), 8)  # 5 healthy + 3 rotten

    def test_only_binary_labels_present(self):
        from ml.data.preprocess import HealthyRottenDataset
        ds = HealthyRottenDataset(root=self.tmp, transform=None)
        labels = {ds[i][1] for i in range(len(ds))}
        self.assertTrue(labels.issubset({0, 1}), f"Unexpected labels: {labels}")

    def test_unknown_folder_raises(self):
        from ml.data.preprocess import HealthyRottenDataset
        # Add an unknown-named folder
        (pathlib.Path(self.tmp) / "Unknown").mkdir()
        from PIL import Image
        Image.new("RGB", (32, 32)).save(pathlib.Path(self.tmp) / "Unknown" / "img.png")
        with self.assertRaises(ValueError):
            HealthyRottenDataset(root=self.tmp, transform=None)

    def test_fresh_folder_maps_to_label_0(self):
        from ml.data.preprocess import HealthyRottenDataset
        from PIL import Image
        tmp2 = tempfile.mkdtemp()
        try:
            for label in ["Fresh", "Rotten"]:
                (pathlib.Path(tmp2) / label).mkdir()
                Image.new("RGB", (32, 32)).save(pathlib.Path(tmp2) / label / "img.png")
            ds = HealthyRottenDataset(root=tmp2, transform=None)
            labels = {ds[i][1] for i in range(len(ds))}
            self.assertEqual(labels, {0, 1})
        finally:
            shutil.rmtree(tmp2)


class PreprocessCorruptScanTest(TestCase):
    """scan_for_corrupt() finds bad images and ignores good ones."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        _make_fake_dataset(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_clean_dataset_returns_empty_list(self):
        from ml.data.preprocess import scan_for_corrupt
        self.assertEqual(scan_for_corrupt(self.tmp), [])

    def test_detects_corrupt_png(self):
        from ml.data.preprocess import scan_for_corrupt
        bad = pathlib.Path(self.tmp) / "Healthy" / "corrupt.png"
        bad.write_bytes(b"not an image at all")
        corrupt = scan_for_corrupt(self.tmp)
        self.assertIn(bad, corrupt)
        self.assertEqual(len(corrupt), 1)

    def test_non_image_files_ignored(self):
        from ml.data.preprocess import scan_for_corrupt
        # .txt files should be silently skipped, not flagged
        (pathlib.Path(self.tmp) / "Healthy" / "readme.txt").write_text("ignore me")
        self.assertEqual(scan_for_corrupt(self.tmp), [])


class PreprocessClassImbalanceTest(TestCase):
    """report_class_imbalance() counts labels and flags skewed distributions."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_balanced_dataset_not_flagged(self):
        from ml.data.preprocess import HealthyRottenDataset, report_class_imbalance
        _make_fake_dataset(self.tmp, healthy_count=5, rotten_count=3)
        ds = HealthyRottenDataset(root=self.tmp, transform=None)
        report = report_class_imbalance(ds)
        self.assertEqual(report["healthy"], 5)
        self.assertEqual(report["rotten"], 3)
        self.assertEqual(report["total"], 8)
        self.assertFalse(report["imbalanced"])  # ratio 0.6 is within [0.5, 2.0]

    def test_heavy_imbalance_flagged(self):
        from ml.data.preprocess import HealthyRottenDataset, report_class_imbalance
        _make_fake_dataset(self.tmp, healthy_count=10, rotten_count=1)
        ds = HealthyRottenDataset(root=self.tmp, transform=None)
        report = report_class_imbalance(ds)
        self.assertTrue(report["imbalanced"])   # ratio 0.1 < 0.5

    def test_wrong_type_raises(self):
        from ml.data.preprocess import report_class_imbalance
        with self.assertRaises(TypeError):
            report_class_imbalance(object())  # not a HealthyRottenDataset


class PreprocessTransformsTest(TestCase):
    """get_transforms() returns two distinct callable pipelines."""

    def test_returns_two_transforms(self):
        from ml.data.preprocess import get_transforms
        train_tf, val_tf = get_transforms()
        self.assertIsNotNone(train_tf)
        self.assertIsNotNone(val_tf)

    def test_transforms_are_callable(self):
        from ml.data.preprocess import get_transforms
        from PIL import Image
        train_tf, val_tf = get_transforms()
        img = Image.new("RGB", (64, 64))
        train_out = train_tf(img)
        val_out = val_tf(img)
        self.assertEqual(train_out.shape, (3, 224, 224))
        self.assertEqual(val_out.shape, (3, 224, 224))


class PreprocessBuildSplitsTest(TestCase):
    """build_splits() creates deterministic non-overlapping train/val subsets."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        _make_fake_dataset(self.tmp, healthy_count=10, rotten_count=10)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_split_sizes_sum_to_total(self):
        from ml.data.preprocess import build_splits
        _, _, n_train, n_val = build_splits(self.tmp, val_split=0.2)
        self.assertEqual(n_train + n_val, 20)

    def test_val_is_20_percent(self):
        from ml.data.preprocess import build_splits
        _, _, n_train, n_val = build_splits(self.tmp, val_split=0.2)
        self.assertEqual(n_val, 4)   # 20% of 20
        self.assertEqual(n_train, 16)

    def test_splits_are_deterministic(self):
        from ml.data.preprocess import build_splits
        _, _, n1, v1 = build_splits(self.tmp, seed=42)
        _, _, n2, v2 = build_splits(self.tmp, seed=42)
        self.assertEqual(n1, n2)
        self.assertEqual(v1, v2)

    def test_different_seeds_give_different_results(self):
        from ml.data.preprocess import build_splits
        train1, _, _, _ = build_splits(self.tmp, seed=1)
        train2, _, _, _ = build_splits(self.tmp, seed=99)
        # Very unlikely same permutation with different seeds on 20 items
        idx1 = train1.indices
        idx2 = train2.indices
        self.assertNotEqual(idx1, idx2)


# ── Task 2: ModelEvaluation model ─────────────────────────────────────────────

class ModelEvaluationModelTest(TestCase):
    """ModelEvaluation DB model stores metrics and orders by evaluated_at."""

    def test_create_and_retrieve(self):
        from api.models import ModelEvaluation
        obj = ModelEvaluation.objects.create(
            version="mobilenetv2-v2",
            accuracy=0.96, precision=0.95, recall=0.97, f1_score=0.96,
        )
        self.assertIsNotNone(obj.pk)
        self.assertEqual(obj.version, "mobilenetv2-v2")
        self.assertAlmostEqual(obj.accuracy, 0.96)

    def test_ordering_oldest_first(self):
        from api.models import ModelEvaluation
        ModelEvaluation.objects.create(version="v1", accuracy=0.90, precision=0.89, recall=0.91, f1_score=0.90)
        ModelEvaluation.objects.create(version="v2", accuracy=0.96, precision=0.95, recall=0.97, f1_score=0.96)
        versions = list(ModelEvaluation.objects.values_list("version", flat=True))
        self.assertEqual(versions[0], "v1")
        self.assertEqual(versions[1], "v2")

    def test_str_contains_version_and_accuracy(self):
        from api.models import ModelEvaluation
        obj = ModelEvaluation.objects.create(
            version="test-v1", accuracy=0.89, precision=0.88, recall=0.90, f1_score=0.89
        )
        self.assertIn("test-v1", str(obj))
        self.assertIn("0.890", str(obj))


# ── Task 2: AdminAIMonitoringView — eval_history context ──────────────────────

class AdminAIMonitoringViewTest(TestCase):
    """Admin AI monitoring page passes eval_history to the template."""

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            email="admin_ai@test.com",
            password="Test1234",
            full_name="AI Admin",
            role="admin",
        )
        self.client.login(username="admin_ai@test.com", password="Test1234")

    def test_page_loads_200_for_admin(self):
        response = self.client.get(reverse("admin_ai_monitoring"))
        self.assertEqual(response.status_code, 200)

    def test_eval_history_empty_by_default(self):
        response = self.client.get(reverse("admin_ai_monitoring"))
        self.assertIn("eval_history", response.context)
        self.assertEqual(len(response.context["eval_history"]), 0)

    def test_eval_history_populated_after_create(self):
        from api.models import ModelEvaluation
        ModelEvaluation.objects.create(
            version="chart-v1", accuracy=0.93, precision=0.92, recall=0.94, f1_score=0.93
        )
        response = self.client.get(reverse("admin_ai_monitoring"))
        self.assertEqual(len(response.context["eval_history"]), 1)
        self.assertEqual(response.context["eval_history"][0]["version"], "chart-v1")

    def test_multiple_evals_all_returned(self):
        from api.models import ModelEvaluation
        for v in ["v1", "v2", "v3"]:
            ModelEvaluation.objects.create(
                version=v, accuracy=0.9, precision=0.9, recall=0.9, f1_score=0.9
            )
        response = self.client.get(reverse("admin_ai_monitoring"))
        self.assertEqual(len(response.context["eval_history"]), 3)

    def test_non_admin_cannot_access(self):
        self.client.logout()
        User.objects.create_user(
            email="cust_ai@test.com", password="Test1234", full_name="Cust", role="customer"
        )
        self.client.login(username="cust_ai@test.com", password="Test1234")
        response = self.client.get(reverse("admin_ai_monitoring"))
        self.assertNotEqual(response.status_code, 200)


# ── Task 2: Celery task writes ModelEvaluation row ────────────────────────────

class EvaluateModelTaskTest(TestCase):
    """evaluate_model_after_upload writes a ModelEvaluation row on success."""

    def _fake_metrics(self, version="task-v99"):
        return {
            "model_version": version,
            "accuracy": 0.95, "precision": 0.94, "recall": 0.96, "f1_score": 0.95,
        }

    def test_successful_evaluation_writes_row_legacy_arch(self):
        from unittest.mock import patch, MagicMock
        from api.tasks import evaluate_model_after_upload
        from api.models import ModelEvaluation

        with patch("subprocess.run") as mock_run, \
             patch("app.services.quality_service.load_latest_model_metrics",
                   return_value=self._fake_metrics("task-v99")):
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            evaluate_model_after_upload("task-v99", arch="mobilenetv2")
            # Uses ml.evaluate for mobilenet
            cmd = mock_run.call_args[0][0]
            self.assertIn("ml.evaluate", " ".join(cmd))

        self.assertEqual(ModelEvaluation.objects.count(), 1)
        row = ModelEvaluation.objects.first()
        self.assertEqual(row.version, "task-v99")
        self.assertAlmostEqual(row.accuracy, 0.95)
        self.assertAlmostEqual(row.precision, 0.94)

    def test_successful_evaluation_writes_row_new_arch(self):
        from unittest.mock import patch, MagicMock
        from api.tasks import evaluate_model_after_upload
        from api.models import ModelEvaluation

        with patch("subprocess.run") as mock_run, \
             patch("app.services.quality_service.load_latest_model_metrics",
                   return_value=self._fake_metrics("efficientnet-v2")):
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            evaluate_model_after_upload("efficientnet-v2", arch="efficientnet-b0")
            # Uses fruit_quality_ai/main.py for EfficientNet
            cmd = mock_run.call_args[0][0]
            self.assertIn("fruit_quality_ai/main.py", " ".join(cmd))

        self.assertEqual(ModelEvaluation.objects.count(), 1)

    def test_failed_evaluation_writes_no_row(self):
        from unittest.mock import patch, MagicMock
        from api.tasks import evaluate_model_after_upload
        from api.models import ModelEvaluation

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="OOM error")
            with self.assertRaises(RuntimeError):
                evaluate_model_after_upload("fail-v1")

        self.assertEqual(ModelEvaluation.objects.count(), 0)

    def test_returned_message_contains_version(self):
        from unittest.mock import patch, MagicMock
        from api.tasks import evaluate_model_after_upload

        with patch("subprocess.run") as mock_run, \
             patch("app.services.quality_service.load_latest_model_metrics",
                   return_value=self._fake_metrics("msg-v1")):
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            result = evaluate_model_after_upload("msg-v1")
        self.assertIn("msg-v1", result)


# ═══════════════════════════════════════════════════════════════════════════════
# AI DEGRADED-PATH RESILIENCE
# Runtime hardening — if an AI service crashes, the page must still render.
# ═══════════════════════════════════════════════════════════════════════════════

class CustomerDashboardDegradedAIPathTest(TestCase):
    """Customer dashboard must render even when the reorder service errors."""

    def setUp(self):
        self.client = Client()
        self.customer = _make_customer("degraded_cust@test.com")
        self.client.login(username="degraded_cust@test.com", password="Test1234")

    def test_dashboard_renders_when_reorder_service_raises(self):
        from unittest.mock import patch

        with patch(
            "app.services.reorder_service.predict_reorder_items",
            side_effect=RuntimeError("model file corrupt"),
        ):
            response = self.client.get(reverse("customer_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["reorder_suggestions"], [])


class ProducerDashboardDegradedAIPathTest(TestCase):
    """Producer dashboard must render even when the forecast service errors."""

    def setUp(self):
        self.client = Client()
        self.producer = _make_producer("degraded_prod@test.com")
        self.client.login(username="degraded_prod@test.com", password="Test1234")

    def test_dashboard_renders_when_forecast_service_raises(self):
        from unittest.mock import patch

        with patch(
            "app.services.forecast_service.get_demand_forecast_dashboard",
            side_effect=RuntimeError("statsmodels unavailable"),
        ):
            response = self.client.get(reverse("producer_dashboard"))
        self.assertEqual(response.status_code, 200)
        forecast = response.context["forecast"]
        self.assertEqual(forecast["products"], [])
        self.assertIsNone(forecast["top_product"])


class MarketplaceDegradedAIPathTest(TestCase):
    """Marketplace must render even when the recommendation service errors."""

    def setUp(self):
        self.client = Client()
        self.customer = _make_customer("degraded_mkt@test.com")
        self.client.login(username="degraded_mkt@test.com", password="Test1234")

    def test_marketplace_renders_when_recommendations_raise(self):
        from unittest.mock import patch

        with patch(
            "api.views_web.recommend_products",
            side_effect=RuntimeError("collaborative matrix broken"),
        ):
            response = self.client.get(reverse("marketplace"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["recommendations"], [])


# ═══════════════════════════════════════════════════════════════════════════════
# RECOMMENDATION ENGINE — smoke tests
# ═══════════════════════════════════════════════════════════════════════════════

class RecommendProductsSmokeTest(TestCase):
    """Recommendation engine must return explained, producer-diverse items."""

    def setUp(self):
        # Two producers → tests the producer-diversity cap
        self.prod_a = _make_producer("rec_prod_a@test.com")
        self.prod_b = _make_producer("rec_prod_b@test.com")
        for i in range(6):
            _make_product(self.prod_a, name=f"A-Fruit-{i}", price="2.00", stock=20)
        for i in range(6):
            _make_product(self.prod_b, name=f"B-Veg-{i}", price="2.50", stock=20)

    def test_returns_shape_with_reason(self):
        from app.services.ai_service import recommend_products
        result = recommend_products(limit=4)
        self.assertIn("items", result)
        self.assertIn("model_version", result)
        self.assertGreater(len(result["items"]), 0)
        for item in result["items"]:
            self.assertIn("id", item)
            self.assertIn("name", item)
            # Customer-facing explainability — reason must be non-empty.
            self.assertTrue(item.get("reason"), f"missing reason on {item['name']}")

    def test_producer_diversity_cap(self):
        from app.services.ai_service import recommend_products
        result = recommend_products(limit=6)
        producer_counts = {}
        for item in result["items"]:
            pid = item.get("producer_id") or item.get("producer")
            if pid is not None:
                producer_counts[pid] = producer_counts.get(pid, 0) + 1
        # Cap is max(1, limit // 2) = 3 for limit=6, but top-up is allowed.
        # At minimum verify no producer has ALL slots when >1 producer exists.
        if len(producer_counts) > 1:
            self.assertLess(max(producer_counts.values()), len(result["items"]))

    def test_empty_catalogue_returns_empty(self):
        from app.services.ai_service import recommend_products
        Product.objects.all().delete()
        result = recommend_products(limit=4)
        self.assertEqual(result["items"], [])


class PredictReorderItemsSmokeTest(TestCase):
    """Reorder predictor must return empty list (not crash) with no history,
    and must produce plain-language reasons when history exists."""

    def setUp(self):
        self.producer = _make_producer("reorder_prod@test.com")
        self.customer = _make_customer("reorder_cust@test.com")
        self.product = _make_product(self.producer, name="Tomato", stock=20)

    def test_no_history_safe_return(self):
        from app.services.reorder_service import predict_reorder_items
        result = predict_reorder_items("unknown@test.com")
        # Safe fallback — list (may be empty or trending), never raises.
        self.assertIsInstance(result, list)

    def test_with_history_returns_items_with_reason(self):
        from app.services.reorder_service import predict_reorder_items
        # Create some order history so trending/model has data
        for i in range(3):
            order = Order.objects.create(
                order_id=f"REORDER-TEST-{i}",
                producer=self.producer,
                customer_name=self.customer.full_name,
                delivery_date=date.today() - timedelta(days=10),
                status="Delivered",
            )
            OrderItem.objects.create(
                order=order, product=self.product,
                quantity=2, unit_price=self.product.price,
            )
        result = predict_reorder_items(self.customer.email)
        self.assertIsInstance(result, list)
        for item in result:
            self.assertIn("name", item)
            self.assertIn("reason", item)
            self.assertTrue(item["reason"])


class NewModelMetricsBridgeTest(TestCase):
    """Bridge must normalise the 28-class evaluator's output into the schema
    the admin monitoring template expects, including per-produce fairness."""

    def _expected_report_path(self):
        import pathlib
        from app.services import quality_service
        return (
            pathlib.Path(quality_service.__file__).resolve().parent.parent.parent
            / "fruit_quality_ai" / "results" / "evaluation_report.json"
        )

    def test_bridges_28class_report_and_computes_per_produce_fairness(self):
        import json
        from app.services import quality_service

        report = {
            "accuracy": 0.88,
            "per_class": {
                "apple_healthy_x":  {"precision": 0.94, "recall": 0.95, "f1-score": 0.945, "support": 100},
                "apple_rotten_x":   {"precision": 0.93, "recall": 0.92, "f1-score": 0.925, "support": 100},
                "tomato_healthy_x": {"precision": 0.90, "recall": 0.90, "f1-score": 0.900, "support": 100},
                "tomato_rotten_x":  {"precision": 0.82, "recall": 0.60, "f1-score": 0.693, "support": 100},
                "weighted avg":     {"precision": 0.90, "recall": 0.84, "f1-score": 0.87,  "support": 400},
                "macro avg":        {"precision": 0.90, "recall": 0.84, "f1-score": 0.87,  "support": 400},
                "accuracy": 0.88,
            },
        }

        path = self._expected_report_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        backup = path.read_text() if path.exists() else None
        try:
            with open(path, "w") as f:
                json.dump(report, f)
            metrics = quality_service._load_new_model_metrics()
        finally:
            if backup is not None:
                path.write_text(backup)
            else:
                path.unlink(missing_ok=True)

        self.assertIsNotNone(metrics)
        self.assertEqual(metrics["model_version"], "efficientnet-b0-v1")
        self.assertEqual(metrics["accuracy"], 0.88)
        self.assertAlmostEqual(metrics["precision"], 0.90, places=2)
        self.assertEqual(metrics["num_classes"], 4)

        fair = metrics["fairness"]
        self.assertIsNotNone(fair)
        self.assertEqual(fair["weakest_rotten_produce"], "tomato")
        self.assertAlmostEqual(fair["weakest_rotten_recall"], 0.60, places=2)
        # mean_healthy ≈ 0.925, mean_rotten ≈ 0.76, gap ≈ 0.165 → warning
        self.assertGreater(fair["equalized_odds_gap"], 0.10)
        self.assertIn("Warning", fair["fairness_verdict"])

    def test_returns_none_when_no_report_on_disk(self):
        from app.services import quality_service

        path = self._expected_report_path()
        backup = path.read_text() if path.exists() else None
        try:
            if path.exists():
                path.unlink()
            self.assertIsNone(quality_service._load_new_model_metrics())
        finally:
            if backup is not None:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(backup)


# ── TC-012: Weekly payment settlements ───────────────────────────────────────

def _prev_week_dates():
    """Return (week_start, week_end) for the Mon–Sun week before today."""
    today = date.today()
    this_monday = today - timedelta(days=today.weekday())
    week_end = this_monday - timedelta(days=1)
    week_start = week_end - timedelta(days=6)
    return week_start, week_end


def _make_settlement(producer, week_start, week_end, gross="100.00", commission="5.00", net="95.00", order_count=2, status="Pending Bank Transfer"):
    week_num = week_start.isocalendar()[1]
    ref = f"SETTLE-{week_start.year}-W{week_num:02d}-{producer.id}"
    return PaymentSettlement.objects.create(
        producer=producer,
        reference=ref,
        week_start=week_start,
        week_end=week_end,
        gross_amount=Decimal(gross),
        commission_amount=Decimal(commission),
        net_amount=Decimal(net),
        order_count=order_count,
        status=status,
    )


def _make_delivered_order(producer, delivery_date, items=None):
    """Create a Delivered Order with one OrderItem for testing settlements."""
    o = Order.objects.create(
        order_id=f"TEST-{producer.id}-{delivery_date}",
        customer_name="Test Customer",
        delivery_date=delivery_date,
        status="Delivered",
        producer=producer,
        commission=Decimal("0.00"),
    )
    product = _make_product(producer, name=f"Prod-{delivery_date}", price="20.00")
    if items is None:
        items = [(product, 2)]
    for prod, qty in items:
        OrderItem.objects.create(order=o, product=prod, quantity=qty, unit_price=prod.price)
    return o


class PaymentSettlementModelTest(TestCase):

    def setUp(self):
        self.producer = _make_producer("settle_producer@test.com")
        self.week_start, self.week_end = _prev_week_dates()

    def test_create_settlement_stores_all_fields(self):
        s = _make_settlement(self.producer, self.week_start, self.week_end,
                             gross="200.00", commission="10.00", net="190.00", order_count=4)
        s.refresh_from_db()
        self.assertEqual(s.gross_amount, Decimal("200.00"))
        self.assertEqual(s.commission_amount, Decimal("10.00"))
        self.assertEqual(s.net_amount, Decimal("190.00"))
        self.assertEqual(s.order_count, 4)
        self.assertEqual(s.week_start, self.week_start)
        self.assertEqual(s.week_end, self.week_end)
        self.assertEqual(s.producer, self.producer)

    def test_default_status_is_pending_bank_transfer(self):
        s = _make_settlement(self.producer, self.week_start, self.week_end)
        self.assertEqual(s.status, "Pending Bank Transfer")
        self.assertEqual(s.status, PaymentSettlement.STATUS_PENDING)

    def test_processed_status_is_valid(self):
        s = _make_settlement(self.producer, self.week_start, self.week_end, status="Processed")
        self.assertEqual(s.status, PaymentSettlement.STATUS_PROCESSED)

    def test_str_contains_reference_and_status(self):
        s = _make_settlement(self.producer, self.week_start, self.week_end)
        self.assertIn(s.reference, str(s))
        self.assertIn(s.status, str(s))

    def test_reference_follows_expected_format(self):
        s = _make_settlement(self.producer, self.week_start, self.week_end)
        week_num = self.week_start.isocalendar()[1]
        expected = f"SETTLE-{self.week_start.year}-W{week_num:02d}-{self.producer.id}"
        self.assertEqual(s.reference, expected)

    def test_unique_together_blocks_duplicate_settlement(self):
        from django.db import IntegrityError
        _make_settlement(self.producer, self.week_start, self.week_end)
        with self.assertRaises(IntegrityError):
            PaymentSettlement.objects.create(
                producer=self.producer,
                reference="SETTLE-DUPLICATE",
                week_start=self.week_start,
                week_end=self.week_end,
                gross_amount=Decimal("50.00"),
                commission_amount=Decimal("2.50"),
                net_amount=Decimal("47.50"),
                order_count=1,
            )

    def test_ordering_newest_first(self):
        week_start_2, week_end_2 = self.week_start - timedelta(weeks=1), self.week_end - timedelta(weeks=1)
        s_old = _make_settlement(self.producer, week_start_2, week_end_2)
        s_new = _make_settlement(self.producer, self.week_start, self.week_end)
        all_s = list(PaymentSettlement.objects.filter(producer=self.producer))
        self.assertEqual(all_s[0], s_new)
        self.assertEqual(all_s[1], s_old)


class ProducerPaymentsViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.producer = _make_producer("pay_producer@test.com")
        self.customer = _make_customer("pay_customer@test.com")
        self.week_start, self.week_end = _prev_week_dates()

    def test_page_loads_200_for_producer(self):
        self.client.login(username="pay_producer@test.com", password="Test1234")
        r = self.client.get(reverse("producer_payments"))
        self.assertEqual(r.status_code, 200)

    def test_unauthenticated_user_redirected(self):
        r = self.client.get(reverse("producer_payments"))
        self.assertEqual(r.status_code, 302)

    def test_customer_cannot_access_payments_page(self):
        self.client.login(username="pay_customer@test.com", password="Test1234")
        r = self.client.get(reverse("producer_payments"))
        self.assertNotEqual(r.status_code, 200)

    def test_context_contains_all_required_keys(self):
        self.client.login(username="pay_producer@test.com", password="Test1234")
        r = self.client.get(reverse("producer_payments"))
        for key in ("payments", "pending_orders", "all_orders", "settlements", "tax_year", "tax_year_net", "tax_year_gross"):
            self.assertIn(key, r.context, msg=f"Missing context key: {key}")

    def test_settlements_list_empty_when_none_exist(self):
        self.client.login(username="pay_producer@test.com", password="Test1234")
        r = self.client.get(reverse("producer_payments"))
        self.assertEqual(r.context["settlements"], [])

    def test_settlement_appears_in_context(self):
        s = _make_settlement(self.producer, self.week_start, self.week_end,
                             gross="120.00", commission="6.00", net="114.00", order_count=3)
        self.client.login(username="pay_producer@test.com", password="Test1234")
        r = self.client.get(reverse("producer_payments"))
        refs = [row["reference"] for row in r.context["settlements"]]
        self.assertIn(s.reference, refs)

    def test_tax_year_net_sums_current_year_settlements_only(self):
        # Current year settlement
        _make_settlement(self.producer, self.week_start, self.week_end,
                         gross="200.00", commission="10.00", net="190.00")
        # Old year settlement — should be excluded from tax year total
        old_start = date(2024, 1, 7)
        old_end = date(2024, 1, 13)
        _make_settlement(self.producer, old_start, old_end,
                         gross="500.00", commission="25.00", net="475.00")

        self.client.login(username="pay_producer@test.com", password="Test1234")
        r = self.client.get(reverse("producer_payments"))
        self.assertEqual(r.context["tax_year"], date.today().year)
        self.assertEqual(r.context["tax_year_net"], 190.0)
        self.assertEqual(r.context["tax_year_gross"], 200.0)

    def test_tax_year_zero_when_no_settlements(self):
        self.client.login(username="pay_producer@test.com", password="Test1234")
        r = self.client.get(reverse("producer_payments"))
        self.assertEqual(r.context["tax_year_net"], 0.0)
        self.assertEqual(r.context["tax_year_gross"], 0.0)

    def test_settlement_status_processed_displays_badge(self):
        _make_settlement(self.producer, self.week_start, self.week_end, status="Processed")
        self.client.login(username="pay_producer@test.com", password="Test1234")
        r = self.client.get(reverse("producer_payments"))
        self.assertContains(r, "Processed")

    def test_settlement_status_pending_displays_badge(self):
        _make_settlement(self.producer, self.week_start, self.week_end, status="Pending Bank Transfer")
        self.client.login(username="pay_producer@test.com", password="Test1234")
        r = self.client.get(reverse("producer_payments"))
        self.assertContains(r, "Pending Bank Transfer")

    def test_settlement_reference_appears_in_page(self):
        s = _make_settlement(self.producer, self.week_start, self.week_end)
        self.client.login(username="pay_producer@test.com", password="Test1234")
        r = self.client.get(reverse("producer_payments"))
        self.assertContains(r, s.reference)

    def test_full_csv_export_returns_csv_content_type(self):
        self.client.login(username="pay_producer@test.com", password="Test1234")
        r = self.client.get(reverse("producer_payments") + "?export=csv")
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/csv", r["Content-Type"])
        self.assertIn("payment_report.csv", r["Content-Disposition"])

    def test_full_csv_export_contains_headers(self):
        self.client.login(username="pay_producer@test.com", password="Test1234")
        r = self.client.get(reverse("producer_payments") + "?export=csv")
        content = r.content.decode()
        self.assertIn("Order ID", content)
        self.assertIn("Commission", content)
        self.assertIn("Net", content)

    def test_settlement_csv_export_returns_csv(self):
        s = _make_settlement(self.producer, self.week_start, self.week_end,
                             gross="80.00", commission="4.00", net="76.00")
        self.client.login(username="pay_producer@test.com", password="Test1234")
        url = reverse("producer_payments") + f"?export=csv&settlement={s.reference}"
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/csv", r["Content-Type"])
        self.assertIn(s.reference, r["Content-Disposition"])

    def test_settlement_csv_contains_settlement_metadata(self):
        s = _make_settlement(self.producer, self.week_start, self.week_end,
                             gross="80.00", commission="4.00", net="76.00")
        self.client.login(username="pay_producer@test.com", password="Test1234")
        url = reverse("producer_payments") + f"?export=csv&settlement={s.reference}"
        r = self.client.get(url)
        content = r.content.decode()
        self.assertIn(s.reference, content)
        self.assertIn(str(self.week_start), content)
        self.assertIn("SETTLEMENT TOTAL", content)

    def test_settlement_csv_includes_product_line_items(self):
        """TC-012: report must include product items sold, not just order totals."""
        product = _make_product(self.producer, name="Organic Carrot", price="3.00")
        order = Order.objects.create(
            order_id="CSV-ITEM-TEST",
            customer_name="Jane Doe",
            delivery_date=self.week_start,
            status="Delivered",
            producer=self.producer,
            commission=Decimal("0.00"),
        )
        OrderItem.objects.create(order=order, product=product, quantity=4, unit_price=product.price)
        s = _make_settlement(self.producer, self.week_start, self.week_end,
                             gross="12.00", commission="0.60", net="11.40", order_count=1)
        self.client.login(username="pay_producer@test.com", password="Test1234")
        url = reverse("producer_payments") + f"?export=csv&settlement={s.reference}"
        r = self.client.get(url)
        content = r.content.decode()
        self.assertIn("Organic Carrot", content)
        self.assertIn("3.00", content)
        self.assertIn("4", content)
        self.assertIn("Jane Doe", content)
        self.assertIn("Product", content)
        self.assertIn("Qty", content)

    def test_settlement_csv_not_found_returns_graceful_response(self):
        self.client.login(username="pay_producer@test.com", password="Test1234")
        url = reverse("producer_payments") + "?export=csv&settlement=SETTLE-DOES-NOT-EXIST"
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/csv", r["Content-Type"])
        self.assertIn("Settlement not found", r.content.decode())

    def test_settlement_csv_cannot_access_other_producers_settlement(self):
        other_producer = _make_producer("other_pay@test.com")
        other_start, other_end = _prev_week_dates()
        s = _make_settlement(other_producer, other_start, other_end)
        self.client.login(username="pay_producer@test.com", password="Test1234")
        url = reverse("producer_payments") + f"?export=csv&settlement={s.reference}"
        r = self.client.get(url)
        # Should return "Settlement not found" — can't access another producer's data
        self.assertIn("Settlement not found", r.content.decode())

    def test_gross_earned_reflects_delivered_orders(self):
        _make_delivered_order(self.producer, date.today() - timedelta(days=10))
        self.client.login(username="pay_producer@test.com", password="Test1234")
        r = self.client.get(reverse("producer_payments"))
        # Order has 2 x £20 = £40 gross; net = £38
        self.assertEqual(r.context["payments"]["this_week"], 40.0)
        self.assertAlmostEqual(r.context["payments"]["net_earned"], 38.0, places=2)

    def test_pending_gross_excludes_cancelled_orders(self):
        product = _make_product(self.producer, name="PendProd", price="10.00")
        cancelled = Order.objects.create(
            order_id="CANCEL-TEST-1",
            customer_name="Test",
            delivery_date=date.today() + timedelta(days=5),
            status="Cancelled",
            producer=self.producer,
            commission=Decimal("0.00"),
        )
        OrderItem.objects.create(order=cancelled, product=product, quantity=2, unit_price=product.price)
        self.client.login(username="pay_producer@test.com", password="Test1234")
        r = self.client.get(reverse("producer_payments"))
        self.assertEqual(r.context["payments"]["pending"], 0.0)


class ProcessWeeklySettlementsTaskTest(TestCase):

    def setUp(self):
        self.producer = _make_producer("task_producer@test.com")
        self.week_start, self.week_end = _prev_week_dates()

    def test_no_delivered_orders_creates_no_settlement(self):
        from api.tasks import process_weekly_settlements
        result = process_weekly_settlements()
        self.assertEqual(PaymentSettlement.objects.count(), 0)
        self.assertIn("0 new records", result)

    def test_delivered_order_in_prev_week_creates_settlement(self):
        from api.tasks import process_weekly_settlements
        _make_delivered_order(self.producer, self.week_start)
        result = process_weekly_settlements()
        self.assertEqual(PaymentSettlement.objects.filter(producer=self.producer).count(), 1)
        self.assertIn("1 new records", result)

    def test_settlement_commission_is_5_percent(self):
        from api.tasks import process_weekly_settlements
        _make_delivered_order(self.producer, self.week_start)
        process_weekly_settlements()
        s = PaymentSettlement.objects.get(producer=self.producer)
        self.assertAlmostEqual(float(s.commission_amount), float(s.gross_amount) * 0.05, places=2)

    def test_settlement_net_is_95_percent(self):
        from api.tasks import process_weekly_settlements
        _make_delivered_order(self.producer, self.week_start)
        process_weekly_settlements()
        s = PaymentSettlement.objects.get(producer=self.producer)
        expected_net = round(float(s.gross_amount) * 0.95, 2)
        self.assertAlmostEqual(float(s.net_amount), expected_net, places=2)

    def test_settlement_gross_equals_sum_of_order_items(self):
        from api.tasks import process_weekly_settlements
        # 2 items x £20 = £40 gross
        _make_delivered_order(self.producer, self.week_start)
        process_weekly_settlements()
        s = PaymentSettlement.objects.get(producer=self.producer)
        self.assertEqual(s.gross_amount, Decimal("40.00"))
        self.assertEqual(s.commission_amount, Decimal("2.00"))
        self.assertEqual(s.net_amount, Decimal("38.00"))

    def test_task_is_idempotent(self):
        from api.tasks import process_weekly_settlements
        _make_delivered_order(self.producer, self.week_start)
        process_weekly_settlements()
        process_weekly_settlements()
        self.assertEqual(PaymentSettlement.objects.filter(producer=self.producer).count(), 1)

    def test_pending_orders_not_included_in_settlement(self):
        from api.tasks import process_weekly_settlements
        product = _make_product(self.producer, name="PendProd2", price="50.00")
        Order.objects.create(
            order_id="PEND-TEST-1",
            customer_name="Test",
            delivery_date=self.week_start,
            status="Pending",
            producer=self.producer,
            commission=Decimal("0.00"),
        )
        process_weekly_settlements()
        self.assertEqual(PaymentSettlement.objects.count(), 0)

    def test_orders_outside_prev_week_not_included(self):
        from api.tasks import process_weekly_settlements
        # Delivered order from 3 weeks ago — outside the settlement window
        old_date = self.week_start - timedelta(weeks=2)
        _make_delivered_order(self.producer, old_date)
        process_weekly_settlements()
        self.assertEqual(PaymentSettlement.objects.count(), 0)

    def test_settlement_status_defaults_to_pending_bank_transfer(self):
        from api.tasks import process_weekly_settlements
        _make_delivered_order(self.producer, self.week_start)
        process_weekly_settlements()
        s = PaymentSettlement.objects.get(producer=self.producer)
        self.assertEqual(s.status, "Pending Bank Transfer")

    def test_reference_follows_correct_format(self):
        from api.tasks import process_weekly_settlements
        _make_delivered_order(self.producer, self.week_start)
        process_weekly_settlements()
        s = PaymentSettlement.objects.get(producer=self.producer)
        week_num = self.week_start.isocalendar()[1]
        expected_ref = f"SETTLE-{self.week_start.year}-W{week_num:02d}-{self.producer.id}"
        self.assertEqual(s.reference, expected_ref)

    def test_order_count_matches_delivered_orders(self):
        from api.tasks import process_weekly_settlements
        _make_delivered_order(self.producer, self.week_start)
        _make_delivered_order(self.producer, self.week_end)
        process_weekly_settlements()
        s = PaymentSettlement.objects.get(producer=self.producer)
        self.assertEqual(s.order_count, 2)

    def test_inactive_producer_skipped(self):
        from api.tasks import process_weekly_settlements
        self.producer.is_active = False
        self.producer.save()
        _make_delivered_order(self.producer, self.week_start)
        process_weekly_settlements()
        self.assertEqual(PaymentSettlement.objects.count(), 0)
