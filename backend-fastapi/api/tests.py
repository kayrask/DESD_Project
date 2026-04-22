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


# ── Task 1: ml/data/preprocess.py — data pipeline ────────────────────────────

import os
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
        import json
        data = {
            "model_version": version,
            "accuracy": 0.95, "precision": 0.94, "recall": 0.96, "f1_score": 0.95,
        }
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump(data, tmp)
        tmp.close()
        return pathlib.Path(tmp.name)

    def test_successful_evaluation_writes_row(self):
        from unittest.mock import patch, MagicMock
        from api.tasks import evaluate_model_after_upload
        from api.models import ModelEvaluation

        metrics_path = self._fake_metrics("task-v99")
        try:
            with patch("subprocess.run") as mock_run, \
                 patch("api.tasks._METRICS_PATH", metrics_path):
                mock_run.return_value = MagicMock(returncode=0, stderr="")
                evaluate_model_after_upload("task-v99")

            self.assertEqual(ModelEvaluation.objects.count(), 1)
            row = ModelEvaluation.objects.first()
            self.assertEqual(row.version, "task-v99")
            self.assertAlmostEqual(row.accuracy, 0.95)
            self.assertAlmostEqual(row.precision, 0.94)
        finally:
            metrics_path.unlink(missing_ok=True)

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

        metrics_path = self._fake_metrics("msg-v1")
        try:
            with patch("subprocess.run") as mock_run, \
                 patch("api.tasks._METRICS_PATH", metrics_path):
                mock_run.return_value = MagicMock(returncode=0, stderr="")
                result = evaluate_model_after_upload("msg-v1")
            self.assertIn("msg-v1", result)
        finally:
            metrics_path.unlink(missing_ok=True)
