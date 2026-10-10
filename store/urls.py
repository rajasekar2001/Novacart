from django.urls import path

from . import views


urlpatterns = [
    path("accounts/login/", views.account_login, name="login"),
    path("accounts/register/", views.customer_register, name="register"),
    path("customer/dashboard/", views.customer_dashboard, name="customer_dashboard"),
    # Staff-only dashboard routes. They are separate from the customer store.
    path("dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("dashboard/categories/", views.admin_categories, name="admin_categories"),
    path(
        "dashboard/categories/<int:category_id>/",
        views.admin_category_detail,
        name="admin_category_detail",
    ),
    path("dashboard/products/", views.admin_products, name="admin_products"),
    path("dashboard/categories/<int:category_id>/delete/", views.admin_category_delete, name="admin_category_delete"),
    path("dashboard/products/<int:product_id>/delete/", views.admin_product_delete, name="admin_product_delete"),
    path("dashboard/products/ai-draft/", views.admin_ai_product_draft, name="admin_ai_product_draft"),
    path("dashboard/ai/category-plan/", views.admin_ai_category_plan, name="admin_ai_category_plan"),
    path("dashboard/ai/quality/", views.admin_quality_insights, name="admin_quality_insights"),
    path("dashboard/ai/copilot/", views.admin_ai_copilot, name="admin_ai_copilot"),
    path(
        "dashboard/products/<int:product_id>/",
        views.admin_product_detail,
        name="admin_product_detail",
    ),
    path(
        "dashboard/products/<int:product_id>/variant/",
        views.admin_product_variant,
        name="admin_product_variant",
    ),
    path("dashboard/inventory/", views.admin_inventory, name="admin_inventory"),

    # Customer storefront routes.
    path("", views.home, name="home"),
    path("category/<slug:slug>/", views.category_products, name="category_products"),
    path("product/<slug:slug>/", views.detail, name="product_detail"),
    path("cart/", views.cart, name="cart"),
    path("cart/add/<int:product_id>/", views.add_cart, name="add_cart"),
    path("cart/update/<path:item_key>/", views.update_cart, name="update_cart"),
    path("cart/remove/<path:item_key>/", views.remove_cart, name="remove_cart"),
    path("checkout/", views.checkout, name="checkout"),
    path("api/pincode/<str:pincode>/", views.pincode_lookup, name="pincode_lookup"),
    path("orders/", views.my_orders, name="my_orders"),
    path("orders/<uuid:public_id>/", views.order_detail, name="order_detail"),
]
