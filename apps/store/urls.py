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
    path("sell/product/<int:pk>/community/", views.offer_community, name="offer_community"),
    path("sell/product/<int:pk>/community/<int:post_id>/comment/", views.offer_community_comment, name="offer_community_comment"),
    path("sell/product/<int:pk>/community/<int:post_id>/delete/", views.offer_community_post_delete, name="offer_community_post_delete"),
    path("sell/product/<int:pk>/community/comment/<int:comment_id>/delete/", views.offer_community_comment_delete, name="offer_community_comment_delete"),
    # Member area
    path("members/", views.portal, name="portal"),
    path("members/login/", views.login, name="login"),
    path("members/logout/", views.logout, name="logout"),
    path("members/set-password/", views.set_password, name="set_password"),
    path("members/forgot/", views.forgot_password, name="forgot_password"),
    path("members/reset/<str:token>/", views.reset_password, name="reset_password"),
    path("members/product/<str:offer_key>/", views.product, name="product"),
    path("members/product/<str:offer_key>/community/", views.community, name="community"),
    path("members/community/post/<int:post_id>/comment/", views.community_comment, name="community_comment"),
    path("members/community/post/<int:post_id>/delete/", views.community_post_delete, name="community_post_delete"),
    path("members/community/comment/<int:comment_id>/delete/", views.community_comment_delete, name="community_comment_delete"),
    path("members/lesson/<int:content_id>/complete/", views.mark_complete, name="mark_complete"),
    path("members/download/<int:content_id>/", views.download, name="download"),
]
