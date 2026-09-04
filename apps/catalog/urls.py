from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("shop/", views.watch_list, name="watch_list"),
    path("shop/<slug:slug>/", views.watch_detail, name="watch_detail"),
    path(
        "shop/<slug:slug>/reviews/",
        views.create_review,
        name="review_create",
    ),
    path("brands/", views.brand_list, name="brand_list"),
    path("brands/<slug:slug>/", views.brand_detail, name="brand_detail"),
    path("collections/", views.collection_list, name="collection_list"),
    path(
        "collections/<slug:slug>/",
        views.collection_detail,
        name="collection_detail",
    ),
    path("search/", views.search, name="search"),
]
