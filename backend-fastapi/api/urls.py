from django.urls import path

from api import views, views_web

# ── REST API endpoints (DRF) ──────────────────────────────────────────────────
api_patterns = [
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
    path("admin-api/commission", views.admin_commission),
    path("dashboards/admin/users", views.dashboards_admin_users),
    path("dashboards/admin/database", views.dashboards_admin_database),
    path("dashboards/customer", views.dashboards_customer),
    path("orders/", views.orders_create),
    path("orders/<int:order_id>", views.orders_get),
    path("ai/recommendations", views.ai_recommendations),
    path("ai/quality-check", views.ai_quality_check),
]

# ── Web (template) URL patterns ───────────────────────────────────────────────
web_patterns = [
    # Public pages
    path("", views_web.HomeView.as_view(), name="home"),
    path("marketplace/", views_web.MarketplaceView.as_view(), name="marketplace"),
    path("for-producers/", views_web.ForProducersView.as_view(), name="for_producers"),
    path("how-it-works/", views_web.HowItWorksView.as_view(), name="how_it_works"),
    path("sustainability/", views_web.SustainabilityView.as_view(), name="sustainability"),
    path("legal/", views_web.LegalView.as_view(), name="legal"),

    # Authentication
    path("login/", views_web.LoginPageView.as_view(), name="login"),
    path("logout/", views_web.LogoutView.as_view(), name="logout"),
    path("register/", views_web.RegisterPageView.as_view(), name="register"),

    # Customer
    path("customer/", views_web.CustomerDashboardView.as_view(), name="customer_dashboard"),
    path("customer/orders/", views_web.CustomerOrdersView.as_view(), name="customer_orders"),
    path("products/", views_web.ProductListView.as_view(), name="product_list"),
    path("products/suggest/", views_web.product_suggest, name="product_suggest"),
    path("search/", views_web.ProductListView.as_view(), name="search"),
    path("products/<int:pk>/", views_web.ProductDetailView.as_view(), name="product_detail"),
    path("cart/", views_web.CartView.as_view(), name="cart"),
    path("cart/add/<int:product_id>/", views_web.AddToCartView.as_view(), name="cart_add"),
    path("cart/remove/<int:product_id>/", views_web.RemoveFromCartView.as_view(), name="cart_remove"),
    path("cart/update/<int:product_id>/", views_web.UpdateCartView.as_view(), name="cart_update"),
    path("checkout/", views_web.CheckoutView.as_view(), name="checkout"),
    path("orders/<int:order_id>/confirmation/", views_web.OrderConfirmationView.as_view(), name="order_confirmation"),
    path("orders/<int:order_id>/receipt/", views_web.OrderReceiptView.as_view(), name="order_receipt"),
    path("orders/<int:order_id>/reorder/", views_web.ReorderView.as_view(), name="order_reorder"),

    # Producer
    path("producer/", views_web.ProducerDashboardView.as_view(), name="producer_dashboard"),
    path("producer/products/", views_web.ProducerProductsView.as_view(), name="producer_products"),
    path("producer/products/<int:pk>/edit/", views_web.ProducerProductEditView.as_view(), name="producer_product_edit"),
    path("producer/orders/", views_web.ProducerOrdersView.as_view(), name="producer_orders"),
    path("producer/orders/<str:order_id>/", views_web.ProducerOrderDetailView.as_view(), name="producer_order_detail"),
    path("producer/orders/<str:order_id>/status/", views_web.ProducerOrderStatusUpdateView.as_view(), name="producer_order_status"),
    path("producer/payments/", views_web.ProducerPaymentsView.as_view(), name="producer_payments"),
    path("producer/quality-check/", views_web.ProducerQualityCheckView.as_view(), name="producer_quality_check"),

    # Admin panel (note: /admin/ is taken by Django admin)
    path("admin-panel/", views_web.AdminDashboardView.as_view(), name="admin_dashboard"),
    path("admin-panel/reports/", views_web.AdminReportsView.as_view(), name="admin_reports"),
    path("admin-panel/users/", views_web.AdminUsersView.as_view(), name="admin_users"),
    path("admin-panel/database/", views_web.AdminDatabaseView.as_view(), name="admin_database"),
    path("admin-panel/ai-monitoring/", views_web.AdminAIMonitoringView.as_view(), name="admin_ai_monitoring"),
    path("admin-panel/ai-monitoring/upload-model/", views_web.AdminModelUploadView.as_view(), name="admin_model_upload"),
    path("admin-panel/ai-monitoring/export-interactions/", views_web.AdminInteractionExportView.as_view(), name="admin_interaction_export"),
    path("admin-panel/ai-monitoring/<int:pk>/", views_web.AdminAIAssessmentDetailView.as_view(), name="admin_ai_assessment_detail"),
    path("admin-panel/ai-confusion-matrix/", views_web.AdminConfusionMatrixView.as_view(), name="admin_ai_confusion_matrix"),

    # Errors
    path("401/", views_web.view_401, name="unauthorized"),
    path("403/", views_web.view_403, name="forbidden"),
]

urlpatterns = api_patterns + web_patterns
