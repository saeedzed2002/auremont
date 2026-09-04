from django.urls import path

from . import views

app_name = "cart"

urlpatterns = [
    path("cart/", views.cart_detail, name="detail"),
    path("cart/add/<slug:slug>/", views.add_to_cart, name="add"),
    path("cart/items/<int:pk>/update/", views.update_cart_item, name="update"),
    path("cart/items/<int:pk>/remove/", views.remove_cart_item, name="remove"),
]
