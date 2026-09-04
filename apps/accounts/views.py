from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models, transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.catalog.models import Watch, WatchImage

from .forms import AddressForm, ProfileForm
from .models import Address, WishlistItem


@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    default_address = request.user.addresses.filter(is_default=True).first()
    return render(
        request,
        "accounts/dashboard.html",
        {"default_address": default_address},
    )


@login_required
def wishlist(request: HttpRequest) -> HttpResponse:
    wishlist_items = request.user.wishlist_items.select_related(
        "watch",
        "watch__brand",
        "watch__category",
    ).prefetch_related(
        models.Prefetch(
            "watch__images",
            queryset=WatchImage.objects.filter(is_primary=True),
        )
    )
    return render(request, "accounts/wishlist.html", {"wishlist_items": wishlist_items})


@login_required
@require_POST
def toggle_wishlist(request: HttpRequest, slug: str) -> HttpResponse:
    watch = get_object_or_404(
        Watch,
        slug=slug,
        is_active=True,
        brand__is_active=True,
        category__is_active=True,
    )
    wishlist_item, created = WishlistItem.objects.get_or_create(
        user=request.user,
        watch=watch,
    )
    if created:
        messages.success(request, f"{watch.name} was saved to your wishlist.")
    else:
        wishlist_item.delete()
        messages.success(request, f"{watch.name} was removed from your wishlist.")

    return redirect(_wishlist_return_url(request, watch))


@login_required
def profile(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated.")
            return redirect("accounts:dashboard")
    else:
        form = ProfileForm(instance=request.user)

    return render(request, "accounts/profile.html", {"form": form})


@login_required
def address_list(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "accounts/address_list.html",
        {"addresses": request.user.addresses.all()},
    )


def save_address(form: AddressForm, user) -> Address:
    with transaction.atomic():
        addresses = Address.objects.select_for_update().filter(user=user)
        address = form.save(commit=False)
        address.user = user

        if not addresses.exists():
            address.is_default = True
        elif address.is_default:
            addresses.exclude(pk=address.pk).update(is_default=False)

        address.save()

    return address


@login_required
def address_create(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = AddressForm(request.POST)
        if form.is_valid():
            save_address(form, request.user)
            messages.success(request, "Your address has been saved.")
            return redirect("accounts:address_list")
    else:
        form = AddressForm()

    return render(
        request,
        "accounts/address_form.html",
        {"form": form, "heading": "Add an address"},
    )


@login_required
def address_update(request: HttpRequest, pk: int) -> HttpResponse:
    address = get_object_or_404(Address, pk=pk, user=request.user)

    if request.method == "POST":
        form = AddressForm(request.POST, instance=address)
        if form.is_valid():
            save_address(form, request.user)
            messages.success(request, "Your address has been updated.")
            return redirect("accounts:address_list")
    else:
        form = AddressForm(instance=address)

    return render(
        request,
        "accounts/address_form.html",
        {"form": form, "heading": "Edit address", "address": address},
    )


@login_required
def address_delete(request: HttpRequest, pk: int) -> HttpResponse:
    address = get_object_or_404(Address, pk=pk, user=request.user)

    if request.method == "POST":
        with transaction.atomic():
            remaining_addresses = (
                Address.objects.select_for_update()
                .filter(user=request.user)
                .exclude(pk=address.pk)
            )
            next_default = remaining_addresses.first() if address.is_default else None
            address.delete()
            if next_default:
                next_default.is_default = True
                next_default.save(update_fields=["is_default", "updated_at"])

        messages.success(request, "Your address has been removed.")
        return redirect("accounts:address_list")

    return render(request, "accounts/address_confirm_delete.html", {"address": address})


def _wishlist_return_url(request: HttpRequest, watch: Watch) -> str:
    next_url = request.POST.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return reverse("catalog:watch_detail", kwargs={"slug": watch.slug})
