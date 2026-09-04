from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from apps.catalog.models import Watch


class Cart(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cart",
        null=True,
        blank=True,
    )
    session_key = models.CharField(max_length=40, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(user__isnull=False, session_key__isnull=True)
                    | Q(user__isnull=True, session_key__isnull=False)
                    & ~Q(session_key="")
                ),
                name="cart_has_exactly_one_owner",
            ),
            models.UniqueConstraint(
                fields=["session_key"],
                condition=Q(session_key__isnull=False),
                name="cart_session_key_unique",
            ),
        ]

    def __str__(self) -> str:
        return self.user.email if self.user else f"Guest cart {self.session_key}"


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    watch = models.ForeignKey(
        Watch, on_delete=models.PROTECT, related_name="cart_items"
    )
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["cart", "watch"],
                name="cart_item_watch_unique",
            ),
            models.CheckConstraint(
                condition=Q(quantity__gt=0),
                name="cart_item_quantity_positive",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.quantity} × {self.watch}"
