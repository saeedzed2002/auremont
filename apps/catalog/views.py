from decimal import Decimal, InvalidOperation

from django.core.paginator import Paginator
from django.db.models import DecimalField, Prefetch, Q
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, render

from .models import Brand, Category, Collection, Watch, WatchImage

CATALOG_PAGE_SIZE = 9
PRICE_FIELD = DecimalField(max_digits=12, decimal_places=2)
SORT_OPTIONS = (
    ("newest", "Newest"),
    ("price_asc", "Price: Low to High"),
    ("price_desc", "Price: High to Low"),
)


def _active_watches():
    return (
        Watch.objects.filter(
            is_active=True,
            brand__is_active=True,
            category__is_active=True,
        )
        .select_related("brand", "category")
        .annotate(
            display_price=Coalesce("discount_price", "price", output_field=PRICE_FIELD)
        )
    )


def _card_watches():
    return _active_watches().prefetch_related(
        Prefetch(
            "images",
            queryset=WatchImage.objects.filter(is_primary=True),
        )
    )


def _decimal_query_value(value: str | None) -> Decimal | None:
    if not value:
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def _filter_watches(request, watches):
    brand = request.GET.get("brand")
    category = request.GET.get("category")
    collection = request.GET.get("collection")
    movement = request.GET.get("movement")
    gender = request.GET.get("gender")
    dial_color = request.GET.get("dial_color")
    strap_material = request.GET.get("strap_material")
    min_price = _decimal_query_value(request.GET.get("min_price"))
    max_price = _decimal_query_value(request.GET.get("max_price"))
    min_diameter = _decimal_query_value(request.GET.get("min_diameter"))
    max_diameter = _decimal_query_value(request.GET.get("max_diameter"))
    water_resistance = request.GET.get("water_resistance")

    if brand:
        watches = watches.filter(brand__slug=brand)
    if category:
        watches = watches.filter(category__slug=category)
    if collection:
        watches = watches.filter(
            collections__slug=collection, collections__is_active=True
        )
    if movement in Watch.Movement.values:
        watches = watches.filter(movement=movement)
    if gender in Watch.Gender.values:
        watches = watches.filter(gender=gender)
    if dial_color:
        watches = watches.filter(dial_color=dial_color)
    if strap_material:
        watches = watches.filter(strap_material=strap_material)
    if min_price is not None:
        watches = watches.filter(display_price__gte=min_price)
    if max_price is not None:
        watches = watches.filter(display_price__lte=max_price)
    if min_diameter is not None:
        watches = watches.filter(case_diameter_mm__gte=min_diameter)
    if max_diameter is not None:
        watches = watches.filter(case_diameter_mm__lte=max_diameter)
    if water_resistance and water_resistance.isdigit():
        watches = watches.filter(water_resistance_m__gte=int(water_resistance))

    sort = request.GET.get("sort", "newest")
    ordering = {
        "newest": ("-created_at",),
        "price_asc": ("display_price", "-created_at"),
        "price_desc": ("-display_price", "-created_at"),
    }.get(sort, ("-created_at",))
    return watches.distinct().order_by(*ordering)


def _filter_options():
    watches = Watch.objects.filter(
        is_active=True,
        brand__is_active=True,
        category__is_active=True,
    )
    return {
        "brands": Brand.objects.filter(is_active=True, watches__in=watches).distinct(),
        "categories": Category.objects.filter(
            is_active=True, watches__in=watches
        ).distinct(),
        "collections": Collection.objects.filter(
            is_active=True,
            watches__in=watches,
        ).distinct(),
        "movements": Watch.Movement.choices,
        "genders": Watch.Gender.choices,
        "dial_colors": watches.order_by("dial_color")
        .values_list("dial_color", flat=True)
        .distinct(),
        "strap_materials": watches.order_by("strap_material")
        .values_list("strap_material", flat=True)
        .distinct(),
    }


def _catalog_context(request, watches, *, heading: str, eyebrow: str, description: str):
    filtered_watches = _filter_watches(request, watches)
    paginator = Paginator(filtered_watches, CATALOG_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))
    query_parameters = request.GET.copy()
    query_parameters.pop("page", None)
    return {
        "page_obj": page_obj,
        "filter_options": _filter_options(),
        "query_string": query_parameters.urlencode(),
        "selected": request.GET,
        "sort_options": SORT_OPTIONS,
        "heading": heading,
        "eyebrow": eyebrow,
        "description": description,
    }


def watch_list(request):
    context = _catalog_context(
        request,
        _card_watches(),
        heading="Watches chosen for their lasting character.",
        eyebrow="Auremont / Collection",
        description=(
            "A considered edit of mechanical, automatic, and quartz watches. "
            "Auremont is an independent demonstration project and is not affiliated "
            "with the displayed brands."
        ),
    )
    return render(request, "catalog/watch_list.html", context)


def watch_detail(request, slug: str):
    watch = get_object_or_404(
        _active_watches().prefetch_related("collections", "images"),
        slug=slug,
    )
    return render(request, "catalog/watch_detail.html", {"watch": watch})


def brand_list(request):
    brands = (
        Brand.objects.filter(
            is_active=True,
            watches__is_active=True,
            watches__category__is_active=True,
        )
        .distinct()
        .order_by("name")
    )
    return render(request, "catalog/brand_list.html", {"brands": brands})


def brand_detail(request, slug: str):
    brand = get_object_or_404(Brand, slug=slug, is_active=True)
    context = _catalog_context(
        request,
        _card_watches().filter(brand=brand),
        heading=brand.name,
        eyebrow="Brand / Auremont",
        description=brand.description
        or "An independent selection presented by Auremont.",
    )
    context["brand"] = brand
    return render(request, "catalog/watch_list.html", context)


def collection_list(request):
    collections = (
        Collection.objects.filter(
            is_active=True,
            watches__is_active=True,
            watches__brand__is_active=True,
            watches__category__is_active=True,
        )
        .distinct()
        .order_by("name")
    )
    return render(request, "catalog/collection_list.html", {"collections": collections})


def collection_detail(request, slug: str):
    collection = get_object_or_404(Collection, slug=slug, is_active=True)
    context = _catalog_context(
        request,
        _card_watches().filter(collections=collection),
        heading=collection.name,
        eyebrow="Collection / Auremont",
        description=collection.description
        or "A focused grouping from the independent Auremont demonstration catalog.",
    )
    context["collection"] = collection
    return render(request, "catalog/watch_list.html", context)


def search(request):
    query = request.GET.get("q", "").strip()
    watches = _card_watches()
    if query:
        watches = watches.filter(
            Q(name__icontains=query)
            | Q(brand__name__icontains=query)
            | Q(collections__name__icontains=query)
            | Q(description__icontains=query)
        )
    else:
        watches = watches.none()

    context = _catalog_context(
        request,
        watches,
        heading="Search the collection",
        eyebrow="Auremont / Search",
        description=(
            "Search by watch, brand, collection, or a detail that matters to you."
        ),
    )
    context["search_query"] = query
    return render(request, "catalog/search.html", context)
