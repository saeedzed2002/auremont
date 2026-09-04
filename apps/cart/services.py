from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from apps.catalog.models import Watch

from .models import Cart, CartItem


class CartValidationError(Exception):
    pass


@dataclass(frozen=True)
class CartLine:
    item: CartItem
    unit_price: Decimal
    total_price: Decimal


@dataclass(frozen=True)
class CartSummary:
    lines: tuple[CartLine, ...]
    item_count: int
    subtotal: Decimal


@dataclass(frozen=True)
class CartMergeResult:
    limited_items: int = 0
    unavailable_items: int = 0

    @property
    def has_adjustments(self) -> bool:
        return bool(self.limited_items or self.unavailable_items)


def find_cart_for_request(request) -> Cart | None:
    if request.user.is_authenticated:
        return Cart.objects.filter(user=request.user).first()

    if request.session.session_key:
        return Cart.objects.filter(session_key=request.session.session_key).first()

    return None


def get_cart_for_request(request) -> Cart:
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        return cart

    if not request.session.session_key:
        request.session.create()

    cart, _ = Cart.objects.get_or_create(session_key=request.session.session_key)
    return cart


def calculate_cart_summary(cart: Cart | None) -> CartSummary:
    if cart is None:
        return CartSummary(lines=(), item_count=0, subtotal=Decimal("0.00"))

    lines = []
    subtotal = Decimal("0.00")
    item_count = 0
    for item in cart.items.select_related("watch", "watch__brand").all():
        unit_price = item.watch.current_price
        total_price = unit_price * item.quantity
        lines.append(
            CartLine(
                item=item,
                unit_price=unit_price,
                total_price=total_price,
            )
        )
        subtotal += total_price
        item_count += item.quantity

    return CartSummary(lines=tuple(lines), item_count=item_count, subtotal=subtotal)


def get_cart_item_count(request) -> int:
    cart = find_cart_for_request(request)
    if cart is None:
        return 0

    return cart.items.aggregate(total=Sum("quantity"))["total"] or 0


def _is_available_for_purchase(watch: Watch) -> bool:
    return watch.is_active and watch.brand.is_active and watch.category.is_active


def _locked_watch(watch_id: int) -> Watch:
    watch = (
        Watch.objects.select_for_update()
        .select_related("brand", "category")
        .filter(pk=watch_id)
        .first()
    )
    if watch is None or not _is_available_for_purchase(watch):
        raise CartValidationError("This watch is no longer available to order.")
    return watch


def _validate_quantity(watch: Watch, quantity: int) -> None:
    if quantity < 1:
        raise CartValidationError("Quantity must be at least one.")
    if quantity > watch.stock:
        raise CartValidationError(
            f"Only {watch.stock} of this watch "
            f"{'is' if watch.stock == 1 else 'are'} available."
        )


def add_watch_to_cart(cart: Cart, watch: Watch, quantity: int) -> CartItem:
    with transaction.atomic():
        locked_cart = Cart.objects.select_for_update().get(pk=cart.pk)
        locked_watch = _locked_watch(watch.pk)
        item = (
            CartItem.objects.select_for_update()
            .filter(cart=locked_cart, watch=locked_watch)
            .first()
        )
        requested_quantity = quantity + (item.quantity if item else 0)
        _validate_quantity(locked_watch, requested_quantity)

        if item is None:
            return CartItem.objects.create(
                cart=locked_cart,
                watch=locked_watch,
                quantity=requested_quantity,
            )

        item.quantity = requested_quantity
        item.save(update_fields=["quantity", "updated_at"])
        return item


def update_cart_item_quantity(cart: Cart, item: CartItem, quantity: int) -> CartItem:
    with transaction.atomic():
        locked_cart = Cart.objects.select_for_update().get(pk=cart.pk)
        locked_item = CartItem.objects.select_for_update().get(
            pk=item.pk,
            cart=locked_cart,
        )
        locked_watch = _locked_watch(locked_item.watch_id)
        _validate_quantity(locked_watch, quantity)
        locked_item.quantity = quantity
        locked_item.save(update_fields=["quantity", "updated_at"])
        return locked_item


def remove_cart_item(cart: Cart, item: CartItem) -> None:
    with transaction.atomic():
        locked_cart = Cart.objects.select_for_update().get(pk=cart.pk)
        CartItem.objects.select_for_update().filter(
            pk=item.pk,
            cart=locked_cart,
        ).delete()


def merge_session_cart_into_user_cart(request, user) -> CartMergeResult:
    session_key = request.session.session_key
    if not session_key:
        return CartMergeResult()

    with transaction.atomic():
        guest_cart = (
            Cart.objects.select_for_update().filter(session_key=session_key).first()
        )
        if guest_cart is None:
            return CartMergeResult()

        user_cart, _ = Cart.objects.get_or_create(user=user)
        user_cart = Cart.objects.select_for_update().get(pk=user_cart.pk)
        limited_items = 0
        unavailable_items = 0

        guest_items = list(
            CartItem.objects.select_for_update().filter(cart=guest_cart).order_by("pk")
        )
        for guest_item in guest_items:
            watch = _locked_watch_or_none(guest_item.watch_id)
            if watch is None or watch.stock == 0:
                unavailable_items += 1
                continue

            user_item = (
                CartItem.objects.select_for_update()
                .filter(cart=user_cart, watch=watch)
                .first()
            )
            existing_quantity = user_item.quantity if user_item else 0
            merged_quantity = min(existing_quantity + guest_item.quantity, watch.stock)
            if merged_quantity < existing_quantity + guest_item.quantity:
                limited_items += 1

            if user_item is None:
                CartItem.objects.create(
                    cart=user_cart,
                    watch=watch,
                    quantity=merged_quantity,
                )
            else:
                user_item.quantity = merged_quantity
                user_item.save(update_fields=["quantity", "updated_at"])

        guest_cart.delete()

    return CartMergeResult(
        limited_items=limited_items,
        unavailable_items=unavailable_items,
    )


def _locked_watch_or_none(watch_id: int) -> Watch | None:
    watch = (
        Watch.objects.select_for_update()
        .select_related("brand", "category")
        .filter(pk=watch_id)
        .first()
    )
    if watch is None or not _is_available_for_purchase(watch):
        return None
    return watch
