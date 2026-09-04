from decimal import Decimal
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

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
                condition=Q(shipping_cost__gte=Decimal("0.00")),
                name="orders_shipping_cost_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(total__gte=Decimal("0.00")),
                name="orders_total_non_negative",
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
