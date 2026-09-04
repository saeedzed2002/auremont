from decimal import ROUND_HALF_UP, Decimal
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.catalog.models import Watch


def generate_order_number() -> str:
    return f"AUR-{uuid4().hex[:12].upper()}"


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending payment"
        PAID = "paid", "Paid"
        PROCESSING = "processing", "Processing"
        SHIPPED = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    TRANSITIONS = {
        Status.PENDING: {Status.PAID, Status.CANCELLED},
        Status.PAID: {Status.PROCESSING, Status.CANCELLED},
        Status.PROCESSING: {Status.SHIPPED, Status.CANCELLED},
        Status.SHIPPED: {Status.DELIVERED},
        Status.DELIVERED: set(),
        Status.CANCELLED: set(),
    }

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orders",
        db_index=False,
    )
    order_number = models.CharField(
        max_length=20,
        unique=True,
        default=generate_order_number,
        editable=False,
    )
    status = models.CharField(max_length=16, choices=Status, default=Status.PENDING)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    discount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    coupon_code = models.CharField(max_length=32, blank=True)
    shipping_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    total = models.DecimalField(max_digits=12, decimal_places=2)
    shipping_full_name = models.CharField(max_length=255)
    shipping_phone = models.CharField(max_length=32)
    shipping_province = models.CharField(max_length=100)
    shipping_city = models.CharField(max_length=100)
    shipping_postal_code = models.CharField(max_length=20)
    shipping_address_line = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "-created_at"])]
        constraints = [
            models.CheckConstraint(
                condition=Q(subtotal__gte=Decimal("0.00")),
                name="orders_subtotal_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(discount__gte=Decimal("0.00")),
                name="orders_discount_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(discount__lte=models.F("subtotal")),
                name="orders_discount_not_above_subtotal",
            ),
            models.CheckConstraint(
                condition=Q(shipping_cost__gte=Decimal("0.00")),
                name="orders_shipping_cost_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(total__gte=Decimal("0.00")),
                name="orders_total_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(
                    total=models.F("subtotal")
                    - models.F("discount")
                    + models.F("shipping_cost")
                ),
                name="orders_total_matches_components",
            ),
        ]

    def __str__(self) -> str:
        return self.order_number

    def transition_to(self, status: Order.Status) -> None:
        if status not in self.TRANSITIONS[self.Status(self.status)]:
            raise ValidationError(
                {"status": f"Cannot transition from {self.status} to {status}."}
            )
        self.status = status
        self.save(update_fields=["status", "updated_at"])


class Coupon(models.Model):
    class DiscountType(models.TextChoices):
        FIXED = "fixed", "Fixed amount"
        PERCENTAGE = "percentage", "Percentage"

    code = models.CharField(max_length=32, unique=True)
    discount_type = models.CharField(max_length=12, choices=DiscountType)
    value = models.DecimalField(max_digits=12, decimal_places=2)
    minimum_order = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(discount_type="fixed", value__gt=Decimal("0.00"))
                    | Q(
                        discount_type="percentage",
                        value__gt=Decimal("0.00"),
                        value__lte=Decimal("100.00"),
                    )
                ),
                name="orders_coupon_value_valid",
            ),
            models.CheckConstraint(
                condition=Q(minimum_order__gte=Decimal("0.00")),
                name="orders_coupon_minimum_order_non_negative",
            ),
            models.CheckConstraint(
                condition=(
                    Q(valid_from__isnull=True)
                    | Q(valid_until__isnull=True)
                    | Q(valid_until__gt=models.F("valid_from"))
                ),
                name="orders_coupon_validity_window_valid",
            ),
        ]

    def __str__(self) -> str:
        return self.code

    def clean(self) -> None:
        super().clean()
        self.code = normalize_coupon_code(self.code)
        errors = {}
        if self.value is not None:
            if self.value <= 0:
                errors["value"] = "Coupon value must be greater than zero."
            elif (
                self.discount_type == self.DiscountType.PERCENTAGE
                and self.value > Decimal("100.00")
            ):
                errors["value"] = "Percentage discounts cannot exceed 100%."
        if self.minimum_order is not None and self.minimum_order < 0:
            errors["minimum_order"] = "Minimum order cannot be negative."
        if self.valid_from and self.valid_until and self.valid_until <= self.valid_from:
            errors["valid_until"] = "Expiry must be later than the start time."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs) -> None:
        self.code = normalize_coupon_code(self.code)
        super().save(*args, **kwargs)

    def validation_error_for(
        self,
        subtotal: Decimal,
        *,
        at=None,
    ) -> str | None:
        current_time = at or timezone.now()
        if not self.is_active:
            return "This coupon is no longer active."
        if self.valid_from and current_time < self.valid_from:
            return "This coupon is not active yet."
        if self.valid_until and current_time >= self.valid_until:
            return "This coupon has expired."
        if subtotal < self.minimum_order:
            return (
                f"This coupon requires an order of at least ${self.minimum_order:.2f}."
            )
        return None

    def discount_for(self, subtotal: Decimal) -> Decimal:
        if self.discount_type == self.DiscountType.PERCENTAGE:
            discount = (subtotal * self.value / Decimal("100.00")).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )
        else:
            discount = self.value
        return min(discount, subtotal)


def normalize_coupon_code(code: str) -> str:
    return code.strip().upper()


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
        db_index=False,
    )
    watch = models.ForeignKey(
        Watch,
        on_delete=models.SET_NULL,
        related_name="order_items",
        null=True,
        blank=True,
    )
    product_name = models.CharField(max_length=180)
    sku = models.CharField(max_length=64)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    total_price = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["order", "watch"],
                name="orders_order_item_watch_unique",
            ),
            models.CheckConstraint(
                condition=Q(unit_price__gt=Decimal("0.00")),
                name="orders_item_unit_price_positive",
            ),
            models.CheckConstraint(
                condition=Q(quantity__gt=0),
                name="orders_item_quantity_positive",
            ),
            models.CheckConstraint(
                condition=Q(total_price__gt=Decimal("0.00")),
                name="orders_item_total_price_positive",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.quantity} × {self.product_name}"
