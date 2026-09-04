from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, render

from .models import Watch, WatchImage


def watch_list(request):
    watches = (
        Watch.objects.filter(is_active=True)
        .select_related("brand", "category")
        .prefetch_related(
            Prefetch(
                "images",
                queryset=WatchImage.objects.filter(is_primary=True),
            )
        )
    )
    return render(request, "catalog/watch_list.html", {"watches": watches})


def watch_detail(request, slug: str):
    watch = get_object_or_404(
        Watch.objects.filter(is_active=True)
        .select_related("brand", "category")
        .prefetch_related("collections", "images"),
        slug=slug,
    )
    return render(request, "catalog/watch_detail.html", {"watch": watch})
