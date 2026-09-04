from django.conf import settings


def authentication(request):
    wishlist_watch_ids = set()
    if request.user.is_authenticated:
        wishlist_watch_ids = set(
            request.user.wishlist_items.values_list("watch_id", flat=True)
        )

    return {
        "google_login_enabled": settings.GOOGLE_LOGIN_ENABLED,
        "wishlist_watch_ids": wishlist_watch_ids,
    }
