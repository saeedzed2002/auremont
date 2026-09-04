from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("checkout/", views.checkout, name="checkout"),
    path("checkout/review/", views.checkout_review, name="checkout_review"),
    path("checkout/payment/", views.mock_payment, name="mock_payment"),
    path("orders/", views.order_history, name="history"),
    path("orders/<str:order_number>/", views.order_detail, name="detail"),
]
