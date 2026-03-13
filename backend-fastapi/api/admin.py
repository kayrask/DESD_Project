from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from api.models import CheckoutOrder, CommissionReport, Order, OrderItem, Product, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("email", "full_name", "role", "status", "is_staff", "date_joined")
    list_filter = ("role", "status", "is_staff")
    search_fields = ("email", "full_name")
    ordering = ("email",)

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal Info", {"fields": ("full_name", "role", "status")}),
        ("Permissions", {"fields": ("is_staff", "is_superuser", "is_active", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "full_name", "role", "password1", "password2"),
        }),
    )


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price", "stock", "status", "producer")
    list_filter = ("category", "status")
    search_fields = ("name", "category", "producer__email")
    ordering = ("name",)
    list_editable = ("price", "stock", "status")


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product", "quantity", "unit_price")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("order_id", "customer_name", "producer", "delivery_date", "status")
    list_filter = ("status",)
    search_fields = ("order_id", "customer_name", "producer__email")
    ordering = ("delivery_date",)
    inlines = [OrderItemInline]


@admin.register(CheckoutOrder)
class CheckoutOrderAdmin(admin.ModelAdmin):
    list_display = ("full_name", "email", "city", "payment_method", "status", "created_at")
    list_filter = ("status", "payment_method")
    search_fields = ("full_name", "email")
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)


@admin.register(CommissionReport)
class CommissionReportAdmin(admin.ModelAdmin):
    list_display = ("report_date", "total_orders", "gross_amount", "commission_amount")
    ordering = ("-report_date",)
