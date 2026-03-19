from rest_framework import serializers

from api.models import CheckoutOrder, CommissionReport, Order, OrderItem, Product, User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "full_name", "role", "status"]
        read_only_fields = ["id"]


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ["email", "password", "full_name", "role"]

    def validate_role(self, value):
        if value not in {"customer", "producer", "admin"}:
            raise serializers.ValidationError("Role must be customer, producer, or admin.")
        return value

    def validate_password(self, value):
        if not any(c.isupper() for c in value):
            raise serializers.ValidationError("Password must contain at least one uppercase letter.")
        if not any(c.islower() for c in value):
            raise serializers.ValidationError("Password must contain at least one lowercase letter.")
        if not any(c.isdigit() for c in value):
            raise serializers.ValidationError("Password must contain at least one digit.")
        return value

    def create(self, validated_data):
        return User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            role=validated_data["role"],
            full_name=validated_data["full_name"],
        )


class ProductSerializer(serializers.ModelSerializer):
    producer_email = serializers.EmailField(source="producer.email", read_only=True)

    class Meta:
        model = Product
        fields = ["id", "name", "category", "price", "stock", "status", "producer_id", "producer_email"]
        read_only_fields = ["id", "producer_id", "producer_email"]

    def validate_price(self, value):
        if value < 0:
            raise serializers.ValidationError("Price must be zero or greater.")
        return value

    def validate_stock(self, value):
        if value < 0:
            raise serializers.ValidationError("Stock must be zero or greater.")
        return value


class ProductCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ["name", "category", "price", "stock", "status"]

    def validate_price(self, value):
        if value < 0:
            raise serializers.ValidationError("Price must be zero or greater.")
        return value

    def validate_stock(self, value):
        if value < 0:
            raise serializers.ValidationError("Stock must be zero or greater.")
        return value


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    line_total = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ["id", "product_id", "product_name", "quantity", "unit_price", "line_total"]

    def get_line_total(self, obj):
        return round(float(obj.unit_price) * obj.quantity, 2)


class OrderSerializer(serializers.ModelSerializer):
    producer_email = serializers.EmailField(source="producer.email", read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)
    order_total = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id", "order_id", "customer_name", "delivery_date",
            "status", "producer_id", "producer_email", "items", "order_total",
        ]
        read_only_fields = ["id", "producer_id", "producer_email"]

    def get_order_total(self, obj):
        return round(sum(
            float(item.unit_price) * item.quantity
            for item in obj.items.all()
        ), 2)


class OrderStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["pending", "confirmed", "ready", "delivered"])


class CheckoutOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = CheckoutOrder
        fields = [
            "id", "full_name", "email", "address", "city",
            "postal_code", "payment_method", "status", "created_at",
        ]
        read_only_fields = ["id", "status", "created_at"]


class CheckoutOrderCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CheckoutOrder
        fields = ["full_name", "email", "address", "city", "postal_code", "payment_method"]

    def validate_email(self, value):
        if "@" not in value:
            raise serializers.ValidationError("Enter a valid email address.")
        return value


class CommissionReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommissionReport
        fields = ["id", "report_date", "total_orders", "gross_amount", "commission_amount"]


# ── Dashboard response serializers ────────────────────────────────────────────
# These serialise the aggregated data returned by dashboard service functions,
# ensuring every API response is shaped and validated through DRF serializers.

class ProducerSummarySerializer(serializers.Serializer):
    orders_today = serializers.IntegerField()
    low_stock_products = serializers.IntegerField()
    quick_links = serializers.ListField(child=serializers.CharField())


class ProducerProductItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    category = serializers.CharField()
    price = serializers.FloatField()
    stock = serializers.IntegerField()
    status = serializers.CharField()


class ProducerProductsResponseSerializer(serializers.Serializer):
    items = ProducerProductItemSerializer(many=True)


class ProducerOrderItemSerializer(serializers.Serializer):
    order_id = serializers.CharField()
    customer = serializers.CharField()
    delivery = serializers.DateField(allow_null=True)
    status = serializers.CharField()


class ProducerOrdersResponseSerializer(serializers.Serializer):
    items = ProducerOrderItemSerializer(many=True)


class ProducerPaymentsSerializer(serializers.Serializer):
    this_week = serializers.FloatField()
    pending = serializers.FloatField()
    commission = serializers.FloatField()


class AdminSummarySerializer(serializers.Serializer):
    commission_today = serializers.FloatField()
    active_users = serializers.IntegerField()
    open_flags = serializers.IntegerField()


class AdminReportRowSerializer(serializers.Serializer):
    date = serializers.DateField()
    orders = serializers.IntegerField()
    gross = serializers.FloatField()
    commission = serializers.FloatField()


class AdminReportsResponseSerializer(serializers.Serializer):
    rows = AdminReportRowSerializer(many=True)


class AdminUserItemSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.CharField()
    status = serializers.CharField()


class AdminUsersResponseSerializer(serializers.Serializer):
    items = AdminUserItemSerializer(many=True)


class CustomerSummarySerializer(serializers.Serializer):
    upcoming_deliveries = serializers.IntegerField()
    saved_producers = serializers.IntegerField()


class AdminDatabaseUserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    email = serializers.EmailField()
    role = serializers.CharField()
    full_name = serializers.CharField()
    status = serializers.CharField()


class AdminDatabaseProductSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    category = serializers.CharField()
    price = serializers.FloatField()
    stock = serializers.IntegerField()
    status = serializers.CharField()
    producer_id = serializers.IntegerField()


class AdminDatabaseOrderSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    order_id = serializers.CharField()
    customer_name = serializers.CharField()
    delivery_date = serializers.DateField(allow_null=True)
    status = serializers.CharField()
    producer_id = serializers.IntegerField()


class AdminDatabaseSerializer(serializers.Serializer):
    users = AdminDatabaseUserSerializer(many=True)
    products = AdminDatabaseProductSerializer(many=True)
    orders = AdminDatabaseOrderSerializer(many=True)
