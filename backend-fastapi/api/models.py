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

ACCOUNT_TYPE_CHOICES = [
    ("individual", "Individual"),
    ("community_group", "Community Group"),
    ("restaurant", "Restaurant"),
]


class User(AbstractUser):
    username = None
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    full_name = models.CharField(max_length=200, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    postal_code = models.CharField(max_length=20, blank=True, default="")
    phone = models.CharField(max_length=30, blank=True, default="")
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPE_CHOICES, default="individual")
    organization_name = models.CharField(max_length=200, blank=True, default="")

    email_verified = models.BooleanField(default=True)

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
        ("Pending Approval", "Pending Approval"),
        ("Rejected", "Rejected"),
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
    discount_percentage = models.IntegerField(default=0, help_text="Manual surplus discount 0–50%")
    ai_discount_percentage = models.IntegerField(default=0, help_text="AI quality discount 0–50%")
    ai_discount_active = models.BooleanField(default=False, help_text="True when the current AI quality discount is active.")
    harvest_date = models.DateField(null=True, blank=True, help_text="Date produce was harvested")
    season_start = models.DateField(null=True, blank=True, help_text="Season availability start")
    season_end = models.DateField(null=True, blank=True, help_text="Season availability end")
    low_stock_threshold = models.IntegerField(default=5, help_text="Alert when stock falls to or below this level")
    surplus_expires_at = models.DateTimeField(null=True, blank=True, help_text="When set, surplus discount expires at this datetime")

    @property
    def discounted_price(self):
        if self.effective_discount_percentage > 0:
            return round(float(self.price) * (1 - self.effective_discount_percentage / 100), 2)
        return None

    @property
    def effective_discount_percentage(self):
        return min(50, max(0, self.discount_percentage) + max(0, self.ai_discount_percentage))

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
    customer = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="vendor_orders"
    )
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
    special_instructions = models.TextField(blank=True, default="")
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


RECURRENCE_CHOICES = [
    ("weekly", "Weekly"),
    ("fortnightly", "Fortnightly"),
]
DAY_CHOICES = [
    (0, "Monday"), (1, "Tuesday"), (2, "Wednesday"),
    (3, "Thursday"), (4, "Friday"), (5, "Saturday"), (6, "Sunday"),
]


class RecurringOrder(models.Model):
    """A scheduled repeat order placed automatically on a recurring basis."""

    STATUS_ACTIVE = "active"
    STATUS_PAUSED = "paused"
    STATUS_CANCELLED = "cancelled"
    STATUS_COMPLETED = "completed"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_PAUSED, "Paused — awaiting approval"),
        (STATUS_CANCELLED, "Cancelled"),
        (STATUS_COMPLETED, "Completed"),
    ]

    PAUSE_PRICE = "price_changed"
    PAUSE_STOCK = "out_of_stock"
    PAUSE_QTY = "quantity_unavailable"
    PAUSE_REASON_CHOICES = [
        (PAUSE_PRICE, "Price changed"),
        (PAUSE_STOCK, "Out of stock"),
        (PAUSE_QTY, "Quantity unavailable"),
    ]

    PREF_AUTO = "auto_continue"
    PREF_NOTIFY = "pause_notify"
    PREF_CHOICES = [
        (PREF_AUTO, "Yes — continue automatically"),
        (PREF_NOTIFY, "No — pause and notify me"),
    ]

    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="recurring_orders")
    items = models.JSONField(help_text='[{"product_id": 1, "name": "...", "quantity": 2, "price": 1.50}]')
    recurrence = models.CharField(max_length=20, choices=RECURRENCE_CHOICES, default="weekly")
    delivery_day = models.IntegerField(choices=DAY_CHOICES, default=2)
    # status replaces the old boolean is_active — kept for backwards compat
    is_active = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    pause_reason = models.CharField(max_length=30, choices=PAUSE_REASON_CHOICES, blank=True, default="")
    on_price_change = models.CharField(
        max_length=20, choices=PREF_CHOICES, default=PREF_NOTIFY,
        help_text="What to do if a product price changes before the order fires",
    )
    on_quantity_change = models.CharField(
        max_length=20, choices=PREF_CHOICES, default=PREF_NOTIFY,
        help_text="What to do if the requested quantity is not fully available",
    )
    end_date = models.DateField(null=True, blank=True, help_text="Recurring order will stop after this date")
    next_order_date = models.DateField()
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Recurring order for {self.customer.full_name} ({self.get_recurrence_display()})"


class RecurringOrderNotification(models.Model):
    """In-app notification for a recurring order event that may require customer action."""

    TYPE_PRICE = "price_changed"
    TYPE_STOCK = "out_of_stock"
    TYPE_QTY = "quantity_unavailable"
    TYPE_PLACED = "order_placed"
    TYPE_CHOICES = [
        (TYPE_PRICE, "Price changed"),
        (TYPE_STOCK, "Out of stock"),
        (TYPE_QTY, "Quantity unavailable"),
        (TYPE_PLACED, "Order placed"),
    ]

    ACTION_APPROVED = "approved"
    ACTION_REJECTED = "rejected"

    recurring_order = models.ForeignKey(
        RecurringOrder, on_delete=models.CASCADE, related_name="notifications"
    )
    notification_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    requires_action = models.BooleanField(default=True)
    action_taken = models.CharField(max_length=20, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.notification_type} notification for order #{self.recurring_order_id}"


SEASON_CHOICES = [
    ("spring", "Spring"),
    ("summer", "Summer"),
    ("autumn", "Autumn/Winter"),
    ("year_round", "Year Round"),
]


class Recipe(models.Model):
    producer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="recipes")
    title = models.CharField(max_length=200)
    description = models.TextField()
    ingredients = models.TextField(help_text="One ingredient per line")
    instructions = models.TextField()
    products = models.ManyToManyField("Product", blank=True, related_name="recipes")
    seasonal_tag = models.CharField(max_length=20, choices=SEASON_CHOICES, default="year_round")
    published_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-published_at"]

    def __str__(self):
        return f"{self.title} by {self.producer.full_name}"


class FarmStory(models.Model):
    producer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="farm_stories")
    title = models.CharField(max_length=200)
    content = models.TextField()
    published_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-published_at"]

    def __str__(self):
        return f"{self.title} by {self.producer.full_name}"


GRADE_OVERRIDE_CHOICES = [
    ("A", "Grade A – Healthy / Premium"),
    ("B", "Grade B – Standard"),
    ("C", "Grade C – Discounted / Borderline"),
]

OVERRIDE_REASON_CHOICES = [
    ("wrong_grade", "AI grade was incorrect"),
    ("context", "Context the model could not see (e.g. variety, age)"),
    ("image_quality", "Poor image quality affected the result"),
    ("other", "Other"),
]


class QualityOverride(models.Model):
    """
    Records when a producer disagrees with the AI quality grade.

    These overrides serve two purposes:
    1. Immediate transparency — the producer's judgement is preserved alongside
       the model prediction so downstream users can see both.
    2. Feedback loop — the override table is the source of ground-truth
       corrections used to prepare new labelled data for model retraining
       (see ml/prepare_feedback.py).

    Producer-parity fairness note: tracking overrides per producer allows us
    to detect if the model systematically mis-grades certain producers' produce,
    which would constitute a fairness issue requiring investigation.
    """
    assessment = models.ForeignKey(
        QualityAssessment, on_delete=models.CASCADE, related_name="overrides"
    )
    producer = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="quality_overrides"
    )
    ai_grade = models.CharField(max_length=1, choices=GRADE_CHOICES)
    override_grade = models.CharField(max_length=1, choices=GRADE_OVERRIDE_CHOICES)
    reason = models.CharField(max_length=30, choices=OVERRIDE_REASON_CHOICES)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"Override by {self.producer.full_name}: "
            f"AI={self.ai_grade} → Producer={self.override_grade}"
        )


class ModelEvaluation(models.Model):
    """Records accuracy metrics each time a model is evaluated after upload."""
    version = models.CharField(max_length=100)
    accuracy = models.FloatField()
    precision = models.FloatField()
    recall = models.FloatField()
    f1_score = models.FloatField()
    evaluated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["evaluated_at"]

    def __str__(self):
        return f"{self.version} acc={self.accuracy:.3f} @ {self.evaluated_at:%Y-%m-%d}"


class PaymentSettlement(models.Model):
    """Weekly payment settlement for a producer.

    Created every Monday morning by the process_weekly_settlements Celery task.
    Covers all delivered orders from the previous Mon–Sun week.
    95% of gross is paid to the producer; 5% is the platform commission.
    """
    STATUS_PENDING = "Pending Bank Transfer"
    STATUS_PROCESSED = "Processed"
    STATUS_CHOICES = [
        ("Pending Bank Transfer", "Pending Bank Transfer"),
        ("Processed", "Processed"),
    ]

    producer = models.ForeignKey(
        "User", on_delete=models.CASCADE, related_name="settlements"
    )
    reference = models.CharField(max_length=60, unique=True)
    week_start = models.DateField()
    week_end = models.DateField()
    gross_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    commission_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    order_count = models.IntegerField(default=0)
    status = models.CharField(
        max_length=30, choices=STATUS_CHOICES, default="Pending Bank Transfer"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-week_start"]
        unique_together = [("producer", "week_start")]

    def __str__(self):
        return f"{self.reference} ({self.status})"


class AdminOTP(models.Model):
    """One-time password for admin two-factor login. Expires after 5 minutes."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="otps")
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"OTP for {self.user.email} ({'used' if self.is_used else 'active'})"


class PasswordResetToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="password_reset_tokens")
    token = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    used = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"PasswordResetToken for {self.user.email} ({'used' if self.used else 'active'})"


class EmailVerificationToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="email_verification_tokens")
    token = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"EmailVerificationToken for {self.user.email}"
