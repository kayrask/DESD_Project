from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, email, password, role, full_name, **kwargs):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, role=role, full_name=full_name, **kwargs)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **kwargs):
        kwargs.setdefault("role", "admin")
        kwargs.setdefault("full_name", "Admin")
        kwargs["is_staff"] = True
        kwargs["is_superuser"] = True
        return self.create_user(email, password, **kwargs)


ROLE_CHOICES = [
    ("producer", "Producer"),
    ("admin", "Admin"),
    ("customer", "Customer"),
]

STATUS_CHOICES = [
    ("active", "Active"),
    ("suspended", "Suspended"),
]


class User(AbstractUser):
    username = None
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    full_name = models.CharField(max_length=200, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    postal_code = models.CharField(max_length=20, blank=True, default="")

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name", "role"]

    objects = UserManager()

    def __str__(self):
        return f"{self.email} ({self.role})"


class Product(models.Model):
    PRODUCT_STATUS_CHOICES = [
        ("Available", "Available"),
        ("In Season", "In Season"),
        ("Out of Stock", "Out of Stock"),
        ("Unavailable", "Unavailable"),
    ]

    name = models.CharField(max_length=200)
    category = models.CharField(max_length=100)
    description = models.TextField(blank=True, default="")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.IntegerField(default=0)
    status = models.CharField(max_length=50, choices=PRODUCT_STATUS_CHOICES, default="Available")
    producer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="products")
    allergens = models.TextField(blank=True, default="", help_text="List allergens e.g. Milk, Eggs, Gluten")
    is_organic = models.BooleanField(default=False)
    discount_percentage = models.IntegerField(default=0, help_text="Surplus/quality discount 0–50%")

    @property
    def discounted_price(self):
        if self.discount_percentage > 0:
            return round(float(self.price) * (1 - self.discount_percentage / 100), 2)
        return None

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.category})"


ORDER_STATUS_CHOICES = [
    ("Pending", "Pending"),
    ("Confirmed", "Confirmed"),
    ("Ready", "Ready"),
    ("Delivered", "Delivered"),
    ("Cancelled", "Cancelled"),
]


class Order(models.Model):
    order_id = models.CharField(max_length=100, unique=True)
    customer_name = models.CharField(max_length=200)
    delivery_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=50, choices=ORDER_STATUS_CHOICES, default="Pending")
    producer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="orders")
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    commission = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        ordering = ["delivery_date"]

    def __str__(self):
        return f"Order {self.order_id} for {self.customer_name}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.quantity}x {self.product.name} in Order {self.order.order_id}"


class CheckoutOrder(models.Model):
    CHECKOUT_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("delivered", "Delivered"),
    ]

    full_name = models.CharField(max_length=200)
    email = models.EmailField()
    address = models.TextField()
    city = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    payment_method = models.CharField(max_length=50)
    delivery_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=50, choices=CHECKOUT_STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    customer = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="checkout_orders"
    )

    def __str__(self):
        return f"Checkout by {self.full_name} ({self.email})"


class CommissionReport(models.Model):
    report_date = models.DateField()
    total_orders = models.IntegerField(default=0)
    gross_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    commission_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        ordering = ["-report_date"]

    def __str__(self):
        return f"Report {self.report_date} — {self.total_orders} orders"


GRADE_CHOICES = [
    ("A", "Grade A – Premium"),
    ("B", "Grade B – Standard"),
    ("C", "Grade C – Discounted"),
]


class CartReservation(models.Model):
    """Tracks how many units of a product each active session has in their cart.
    Used to soft-reserve stock so concurrent customers cannot over-commit."""
    session_key = models.CharField(max_length=40, db_index=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="cart_reservations")
    quantity = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("session_key", "product")

    def __str__(self):
        return f"Session {self.session_key[:8]}… — {self.quantity}x {self.product.name}"


class QualityAssessment(models.Model):
    """
    Stores the result of an AI quality check performed on a producer's product image.
    The CNN model classifies the image as Healthy/Rotten and maps confidence to A/B/C.
    """
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="quality_assessments")
    assessed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="assessments")
    image = models.ImageField(upload_to="quality_checks/")
    grade = models.CharField(max_length=1, choices=GRADE_CHOICES)
    color_score = models.FloatField(help_text="Colour uniformity score 0–100")
    size_score = models.FloatField(help_text="Size / shape score 0–100")
    ripeness_score = models.FloatField(help_text="Ripeness / freshness score 0–100")
    model_confidence = models.FloatField(help_text="CNN softmax confidence 0–1")
    model_version = models.CharField(max_length=50, default="mobilenetv2-v1")
    is_healthy = models.BooleanField()
    notes = models.TextField(blank=True, default="")
    quantity_lost = models.IntegerField(default=0)
    assessed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-assessed_at"]

    def __str__(self):
        return f"{self.product.name} → Grade {self.grade} ({self.model_confidence:.0%} conf)"


class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reviews")
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reviews")
    rating = models.IntegerField(choices=[(i, f"{i} star{'s' if i > 1 else ''}") for i in range(1, 6)])
    title = models.CharField(max_length=200, blank=True, default="")
    text = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("product", "customer")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.customer.full_name} → {self.product.name} ({self.rating}★)"
