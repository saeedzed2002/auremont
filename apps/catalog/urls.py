from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("shop/", views.watch_list, name="watch_list"),
    path("shop/<slug:slug>/", views.watch_detail, name="watch_detail"),
]
