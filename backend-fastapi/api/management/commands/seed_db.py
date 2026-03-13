"""
Usage:
    python manage.py seed_db

Creates the demo users, products, orders, and commission reports used in
sprint demos. Safe to run multiple times — existing records are skipped.
"""

from django.core.management.base import BaseCommand

from api.models import CommissionReport, Order, Product, User


class Command(BaseCommand):
    help = "Seed the database with demo data for sprint demonstrations"

    def handle(self, *args, **options):
        self.stdout.write("Seeding database...")

        # ── Django superuser (for /admin/ panel) ─────────────────────────────
        if not User.objects.filter(email="superadmin@desd.local").exists():
            User.objects.create_superuser(
                email="superadmin@desd.local",
                password="Admin1234",
                full_name="Super Admin",
                role="admin",
            )
            self.stdout.write("  created superuser: superadmin@desd.local / Admin1234")
        else:
            self.stdout.write("  skip superuser: superadmin@desd.local")

        # ── Users ────────────────────────────────────────────────────────────
        producer = self._get_or_create_user(
            email="producer@desd.local",
            password="Password123",
            role="producer",
            full_name="Producer User",
        )
        self._get_or_create_user(
            email="admin@desd.local",
            password="Password123",
            role="admin",
            full_name="Admin User",
        )
        self._get_or_create_user(
            email="customer@desd.local",
            password="Password123",
            role="customer",
            full_name="Customer User",
        )
        self._get_or_create_user(
            email="suspended@desd.local",
            password="Password123",
            role="customer",
            full_name="Suspended User",
            status="suspended",
        )

        # ── Products ─────────────────────────────────────────────────────────
        self._get_or_create_product(
            producer=producer,
            name="Heirloom Tomatoes",
            category="Vegetable",
            price=4.50,
            stock=52,
            status="Available",
        )
        self._get_or_create_product(
            producer=producer,
            name="Winter Kale",
            category="Leafy Greens",
            price=3.20,
            stock=0,
            status="Out of Stock",
        )
        self._get_or_create_product(
            producer=producer,
            name="Organic Carrots",
            category="Vegetable",
            price=2.80,
            stock=34,
            status="Available",
        )
        self._get_or_create_product(
            producer=producer,
            name="Free-Range Eggs (dozen)",
            category="Dairy & Eggs",
            price=3.90,
            stock=20,
            status="Available",
        )

        # ── Orders ───────────────────────────────────────────────────────────
        self._get_or_create_order(
            producer=producer,
            order_id="D-1023",
            customer_name="John Smith",
            delivery_date="2026-03-06",
            status="Pending",
        )
        self._get_or_create_order(
            producer=producer,
            order_id="D-1019",
            customer_name="Jane Doe",
            delivery_date="2026-03-05",
            status="Confirmed",
        )
        self._get_or_create_order(
            producer=producer,
            order_id="D-1031",
            customer_name="Alice Brown",
            delivery_date="2026-03-10",
            status="Pending",
        )

        # ── Commission Reports ────────────────────────────────────────────────
        self._get_or_create_report("2026-03-01", 24, 4820.00, 482.00)
        self._get_or_create_report("2026-02-28", 19, 3110.00, 311.00)
        self._get_or_create_report("2026-02-21", 22, 4100.00, 410.00)

        self.stdout.write(self.style.SUCCESS("Database seeded successfully."))

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_or_create_user(self, email, password, role, full_name, status="active"):
        if User.objects.filter(email=email).exists():
            self.stdout.write(f"  skip user: {email}")
            return User.objects.get(email=email)
        user = User.objects.create_user(
            email=email,
            password=password,
            role=role,
            full_name=full_name,
            status=status,
        )
        self.stdout.write(f"  created user: {email}")
        return user

    def _get_or_create_product(self, producer, name, category, price, stock, status):
        obj, created = Product.objects.get_or_create(
            name=name,
            producer=producer,
            defaults={"category": category, "price": price, "stock": stock, "status": status},
        )
        label = "created" if created else "skip"
        self.stdout.write(f"  {label} product: {name}")
        return obj

    def _get_or_create_order(self, producer, order_id, customer_name, delivery_date, status):
        obj, created = Order.objects.get_or_create(
            order_id=order_id,
            defaults={
                "producer": producer,
                "customer_name": customer_name,
                "delivery_date": delivery_date,
                "status": status,
            },
        )
        label = "created" if created else "skip"
        self.stdout.write(f"  {label} order: {order_id}")
        return obj

    def _get_or_create_report(self, report_date, total_orders, gross, commission):
        obj, created = CommissionReport.objects.get_or_create(
            report_date=report_date,
            defaults={
                "total_orders": total_orders,
                "gross_amount": gross,
                "commission_amount": commission,
            },
        )
        label = "created" if created else "skip"
        self.stdout.write(f"  {label} report: {report_date}")
        return obj
