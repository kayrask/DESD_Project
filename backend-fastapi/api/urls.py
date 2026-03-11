from django.urls import path

from api import views

urlpatterns = [
    path("health", views.health),
    path("auth/login", views.auth_login),
    path("auth/register", views.auth_register),
    path("auth/logout", views.auth_logout),
    path("dashboards/me", views.dashboards_me),
    path("dashboards/producer", views.dashboards_producer),
    path("dashboards/producer/products", views.dashboards_producer_products),
    path("dashboards/producer/orders", views.dashboards_producer_orders),
    path("dashboards/producer/payments", views.dashboards_producer_payments),
    path("producer/products", views.producer_products_create),
    path("producer/products/<int:product_id>", views.producer_products_update),
    path("producer/orders/<str:order_id>", views.producer_order_get),
    path("producer/orders/<str:order_id>/status", views.producer_order_status_update),
    path("dashboards/admin", views.dashboards_admin),
    path("dashboards/admin/reports", views.dashboards_admin_reports),
    path("dashboards/admin/users", views.dashboards_admin_users),
    path("dashboards/admin/database", views.dashboards_admin_database),
    path("dashboards/customer", views.dashboards_customer),
    path("orders/", views.orders_create),
    path("orders/<int:order_id>", views.orders_get),
    path("ai/recommendations", views.ai_recommendations),
]
