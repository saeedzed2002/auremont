from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.accounts.urls")),
    path("", include("apps.cart.urls")),
    path("", include("apps.orders.urls")),
    path("accounts/", include("allauth.urls")),
    path("", include("apps.catalog.urls")),
    path("", include("apps.core.urls")),
]

handler404 = "apps.core.views.page_not_found"
handler500 = "apps.core.views.server_error"

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
