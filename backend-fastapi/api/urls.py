from django.urls import path, re_path

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
    path("api/products", views.products_list),
    path("api/products/<int:product_id>", views.product_detail),
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
    path("login/otp/", views_web.AdminOTPVerifyView.as_view(), name="admin_otp_verify"),
    path("logout/", views_web.LogoutView.as_view(), name="logout"),
    path("register/", views_web.RegisterPageView.as_view(), name="register"),
    path("forgot-password/", views_web.ForgotPasswordView.as_view(), name="forgot_password"),
    path("reset-password/<str:token>/", views_web.PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("verify-email/<str:token>/", views_web.VerifyEmailView.as_view(), name="verify_email"),
    path("email-verify-pending/", views_web.EmailVerifyPendingView.as_view(), name="email_verify_pending"),

    # Customer
    path("customer/", views_web.CustomerDashboardView.as_view(), name="customer_dashboard"),
    path("customer/orders/", views_web.CustomerOrdersView.as_view(), name="customer_orders"),
    path("products/", views_web.ProductListView.as_view(), name="product_list"),
    path("products/suggest/", views_web.product_suggest, name="product_suggest"),
    path("search/", views_web.ProductListView.as_view(), name="search"),
    path("products/<int:pk>/", views_web.ProductDetailView.as_view(), name="product_detail"),
    path("producers/<int:pk>/", views_web.ProducerProfileView.as_view(), name="producer_profile"),
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
    path("producer/content/", views_web.ProducerRecipesView.as_view(), name="producer_content"),
    path("producer/demand-forecast/", views_web.ProducerDemandForecastView.as_view(), name="producer_demand_forecast"),
    path("recipes/<int:pk>/", views_web.RecipeDetailView.as_view(), name="recipe_detail"),

    # Customer recurring orders
    path("customer/recurring-orders/", views_web.RecurringOrdersView.as_view(), name="recurring_orders"),
    path("customer/recurring-orders/<int:pk>/cancel/", views_web.CancelRecurringOrderView.as_view(), name="recurring_order_cancel"),
    path("customer/recurring-orders/notifications/", views_web.RecurringOrderNotificationsView.as_view(), name="recurring_order_notifications"),
    path("customer/recurring-orders/notifications/<int:pk>/approve/", views_web.RecurringOrderApproveView.as_view(), name="recurring_order_approve"),

    # Admin panel (note: /admin/ is taken by Django admin)
    path("admin-panel/", views_web.AdminDashboardView.as_view(), name="admin_dashboard"),
    path("admin-panel/products/", views_web.AdminProductApprovalView.as_view(), name="admin_product_approval"),
    path("admin-panel/reports/", views_web.AdminReportsView.as_view(), name="admin_reports"),
    path("admin-panel/users/", views_web.AdminUsersView.as_view(), name="admin_users"),
    path("admin-panel/users/approval/", views_web.AdminUserApprovalView.as_view(), name="admin_user_approval"),
    path("admin-panel/users/<int:pk>/delete/", views_web.AdminDeleteUserView.as_view(), name="admin_delete_user"),
    path("account/settings/", views_web.AccountSettingsView.as_view(), name="account_settings"),
    path("account/delete/", views_web.DeleteAccountView.as_view(), name="delete_account"),
    path("admin-panel/test-email/", views_web.AdminTestEmailView.as_view(), name="admin_test_email"),
    path("admin-panel/database/", views_web.AdminDatabaseView.as_view(), name="admin_database"),
    path("admin-panel/ai-monitoring/", views_web.AdminAIMonitoringView.as_view(), name="admin_ai_monitoring"),
    path("admin-panel/ai-monitoring/upload-model/", views_web.AdminModelUploadView.as_view(), name="admin_model_upload"),
    path("admin-panel/ai-monitoring/export-interactions/", views_web.AdminInteractionExportView.as_view(), name="admin_interaction_export"),
    path("admin-panel/ai-monitoring/<int:pk>/", views_web.AdminAIAssessmentDetailView.as_view(), name="admin_ai_assessment_detail"),
    path("admin-panel/ai-confusion-matrix/", views_web.AdminConfusionMatrixView.as_view(), name="admin_ai_confusion_matrix"),
    path("admin-panel/override-review/", views_web.AdminOverrideReviewView.as_view(), name="admin_override_review"),

    # Errors
    path("401/", views_web.view_401, name="unauthorized"),
    path("403/", views_web.view_403, name="forbidden"),
]

# Catch-all — must be last so it only fires when nothing above matched.
# Works in both DEBUG=True and DEBUG=False (handler404 alone only fires in prod).
_catch_all = [
    re_path(r"^.*$", views_web.view_404, name="not_found"),
]

urlpatterns = api_patterns + web_patterns + _catch_all
