from django.urls import path

from . import views

app_name = "store"

urlpatterns = [
    # Public checkout
    path("buy/<str:offer_key>/", views.buy, name="buy"),
    path("checkout/success/", views.checkout_success, name="checkout_success"),
    path("checkout/cancel/", views.checkout_cancel, name="checkout_cancel"),
    path("stripe/webhook/", views.stripe_webhook, name="stripe_webhook"),
    # Creator dashboard
    path("sell/customers/", views.customers_dashboard, name="customers"),
    # Member area
    path("members/", views.portal, name="portal"),
    path("members/login/", views.login, name="login"),
    path("members/logout/", views.logout, name="logout"),
    path("members/set-password/", views.set_password, name="set_password"),
    path("members/forgot/", views.forgot_password, name="forgot_password"),
    path("members/reset/<str:token>/", views.reset_password, name="reset_password"),
    path("members/product/<str:offer_key>/", views.product, name="product"),
    path("members/download/<int:content_id>/", views.download, name="download"),
]
