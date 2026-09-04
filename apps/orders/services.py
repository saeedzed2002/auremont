from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction

from apps.cart.models import Cart, CartItem
from apps.cart.services import CartSummary, calculate_cart_summary
from apps.catalog.models import Watch

from .models import Coupon, Order, OrderItem, normalize_coupon_code

COMPLIMENTARY_SHIPPING = Decimal("0.00")
REQUIRED_SHIPPING_FIELDS = (
    "full_name",
    "phone",
    "province",
    "city",
    "postal_code",
    "address_line",
)


class CheckoutValidationError(Exception):
    pass


class CouponValidationError(CheckoutValidationError):
    pass


@dataclass(frozen=True)
class CheckoutSummary:
    cart_summary: CartSummary
    coupon: Coupon | None
    discount: Decimal
    shipping_cost: Decimal
    total: Decimal


def checkout_summary(
    cart: Cart | None,
    *,
    coupon_code: str | None = None,
) -> CheckoutSummary:
    validate_cart_for_checkout(cart)
    cart_summary = calculate_cart_summary(cart)
    coupon, discount = apply_coupon(coupon_code, cart_summary.subtotal)
    return CheckoutSummary(
        cart_summary=cart_summary,
        coupon=coupon,
        discount=discount,
        shipping_cost=COMPLIMENTARY_SHIPPING,
        total=cart_summary.subtotal - discount + COMPLIMENTARY_SHIPPING,
    )


def apply_coupon(
    coupon_code: str | None,
    subtotal: Decimal,
    *,
    lock: bool = False,
) -> tuple[Coupon | None, Decimal]:
    if not coupon_code:
        return None, Decimal("0.00")

    code = normalize_coupon_code(coupon_code)
    coupons = Coupon.objects.select_for_update() if lock else Coupon.objects
    coupon = coupons.filter(code=code).first()
    if coupon is None:
        raise CouponValidationError("This coupon code is not valid.")

    validation_error = coupon.validation_error_for(subtotal)
    if validation_error:
        raise CouponValidationError(validation_error)
    return coupon, coupon.discount_for(subtotal)


def validate_cart_for_checkout(cart: Cart | None) -> None:
    if cart is None:
        raise CheckoutValidationError("Your cart is empty.")

    items = list(cart.items.select_related("watch", "watch__brand", "watch__category"))
    if not items:
        raise CheckoutValidationError("Your cart is empty.")

    for item in items:
        watch = item.watch
        if not _watch_is_available(watch):
            raise CheckoutValidationError(
                f"{watch.name} is no longer available to order."
            )
        if item.quantity > watch.stock:
            raise CheckoutValidationError(
                f"Only {watch.stock} of {watch.name} "
                f"{'is' if watch.stock == 1 else 'are'} available."
            )


def create_paid_order(
    *,
    user,
    cart: Cart | None,
    shipping_address: dict[str, str],
    coupon_code: str | None = None,
) -> Order:
    _validate_shipping_address(shipping_address)
    if cart is None:
        raise CheckoutValidationError("Your cart is empty.")

    with transaction.atomic():
        locked_cart = (
            Cart.objects.select_for_update().filter(pk=cart.pk, user=user).first()
        )
        if locked_cart is None:
            raise CheckoutValidationError("Your cart is no longer available.")

        cart_items = list(
            CartItem.objects.select_for_update()
            .filter(cart=locked_cart)
            .order_by("watch_id")
        )
        if not cart_items:
            raise CheckoutValidationError("Your cart is empty.")

        watch_ids = [item.watch_id for item in cart_items]
        locked_watches = {
            watch.pk: watch
            for watch in Watch.objects.select_for_update()
            .select_related("brand", "category")
            .filter(pk__in=watch_ids)
            .order_by("pk")
        }

        order_lines = []
        subtotal = Decimal("0.00")
        for cart_item in cart_items:
            watch = locked_watches.get(cart_item.watch_id)
            if watch is None or not _watch_is_available(watch):
                raise CheckoutValidationError(
                    "A watch in your cart is no longer available to order."
                )
            if cart_item.quantity > watch.stock:
                raise CheckoutValidationError(
                    f"Only {watch.stock} of {watch.name} "
                    f"{'is' if watch.stock == 1 else 'are'} available."
                )

            unit_price = watch.current_price
            total_price = unit_price * cart_item.quantity
            subtotal += total_price
            order_lines.append(
                OrderItem(
                    watch=watch,
                    product_name=f"{watch.brand.name} {watch.name}",
                    sku=watch.sku,
                    unit_price=unit_price,
                    quantity=cart_item.quantity,
                    total_price=total_price,
                )
            )

        coupon, discount = apply_coupon(coupon_code, subtotal, lock=True)
        order = Order.objects.create(
            user=user,
            status=Order.Status.PAID,
            subtotal=subtotal,
            discount=discount,
            coupon_code=coupon.code if coupon else "",
            shipping_cost=COMPLIMENTARY_SHIPPING,
            total=subtotal - discount + COMPLIMENTARY_SHIPPING,
            shipping_full_name=shipping_address["full_name"],
            shipping_phone=shipping_address["phone"],
            shipping_province=shipping_address["province"],
            shipping_city=shipping_address["city"],
            shipping_postal_code=shipping_address["postal_code"],
            shipping_address_line=shipping_address["address_line"],
        )
        for order_line in order_lines:
            order_line.order = order
        OrderItem.objects.bulk_create(order_lines)

        for cart_item in cart_items:
            watch = locked_watches[cart_item.watch_id]
            watch.stock -= cart_item.quantity
            watch.save(update_fields=["stock", "updated_at"])
        CartItem.objects.filter(pk__in=[item.pk for item in cart_items]).delete()

    return order


def _watch_is_available(watch: Watch) -> bool:
    return watch.is_active and watch.brand.is_active and watch.category.is_active


def _validate_shipping_address(shipping_address: dict[str, str]) -> None:
    if any(
        not shipping_address.get(field_name, "").strip()
        for field_name in REQUIRED_SHIPPING_FIELDS
    ):
        raise CheckoutValidationError("Your delivery address is incomplete.")
