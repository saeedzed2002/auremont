from django.db.models import Count, Prefetch, Q
from django.shortcuts import render

from apps.catalog.models import Collection, Watch, WatchImage


def home(request):
    watches = (
        Watch.objects.filter(
            is_active=True,
            brand__is_active=True,
            category__is_active=True,
        )
        .select_related("brand", "category")
        .prefetch_related(
            Prefetch(
                "images",
                queryset=WatchImage.objects.filter(is_primary=True),
            )
        )
    )
    return render(
        request,
        "core/home.html",
        {
            "featured_watches": watches.filter(is_featured=True)[:4],
            "new_arrivals": watches[:3],
            "collections": Collection.objects.filter(is_active=True)
            .annotate(
                watch_count=Count(
                    "watches",
                    filter=Q(
                        watches__is_active=True,
                        watches__brand__is_active=True,
                        watches__category__is_active=True,
                    ),
                )
            )
            .filter(watch_count__gt=0)[:3],
        },
    )


def page_not_found(request, exception):
    return render(request, "404.html", status=404)


def server_error(request):
    return render(request, "500.html", status=500)
