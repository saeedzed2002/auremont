from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.catalog.models import Watch

from .forms import CartQuantityForm
from .models import CartItem
from .services import (
    CartValidationError,
    add_watch_to_cart,
    calculate_cart_summary,
    find_cart_for_request,
    get_cart_for_request,
    update_cart_item_quantity,
)
from .services import remove_cart_item as remove_cart_item_service


def cart_detail(request: HttpRequest) -> HttpResponse:
    cart = find_cart_for_request(request)
    return render(
        request,
        "cart/detail.html",
        {
            "summary": calculate_cart_summary(cart),
        },
    )


@require_POST
def add_to_cart(request: HttpRequest, slug: str) -> HttpResponse:
    watch = get_object_or_404(
        Watch.objects.select_related("brand", "category"),
        slug=slug,
        is_active=True,
        brand__is_active=True,
        category__is_active=True,
    )
    form = CartQuantityForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Choose a whole quantity of at least one.")
        return redirect(_return_url(request, watch))

    try:
        add_watch_to_cart(
            get_cart_for_request(request),
            watch,
            form.cleaned_data["quantity"],
        )
    except CartValidationError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, f"{watch.name} was added to your cart.")

    return redirect(_return_url(request, watch))


@require_POST
def update_cart_item(request: HttpRequest, pk: int) -> HttpResponse:
    cart = find_cart_for_request(request)
    if cart is None:
        return redirect("cart:detail")

    item = get_object_or_404(CartItem, pk=pk, cart=cart)
    form = CartQuantityForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Choose a whole quantity of at least one.")
        return redirect("cart:detail")

    try:
        update_cart_item_quantity(cart, item, form.cleaned_data["quantity"])
    except CartValidationError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, "Cart quantity updated.")

    return redirect("cart:detail")


@require_POST
def remove_cart_item(request: HttpRequest, pk: int) -> HttpResponse:
    cart = find_cart_for_request(request)
    if cart is None:
        return redirect("cart:detail")

    item = get_object_or_404(CartItem, pk=pk, cart=cart)
    remove_cart_item_service(cart, item)
    messages.success(request, "Watch removed from your cart.")
    return redirect("cart:detail")


def _return_url(request: HttpRequest, watch: Watch) -> str:
    next_url = request.POST.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return reverse("catalog:watch_detail", kwargs={"slug": watch.slug})
