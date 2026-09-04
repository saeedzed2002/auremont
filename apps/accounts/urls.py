from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("account/", views.dashboard, name="dashboard"),
    path("account/profile/", views.profile, name="profile"),
    path("account/addresses/", views.address_list, name="address_list"),
    path("account/addresses/add/", views.address_create, name="address_create"),
    path(
        "account/addresses/<int:pk>/edit/",
        views.address_update,
        name="address_update",
    ),
    path(
        "account/addresses/<int:pk>/delete/",
        views.address_delete,
        name="address_delete",
    ),
]
