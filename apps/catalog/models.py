from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _


class Brand(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to="brands/", blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Category(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def __str__(self) -> str:
        return self.name


class Collection(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Watch(models.Model):
    class Movement(models.TextChoices):
        AUTOMATIC = "automatic", _("Automatic")
        MECHANICAL = "mechanical", _("Mechanical")
        QUARTZ = "quartz", _("Quartz")

    class Gender(models.TextChoices):
        WOMEN = "women", _("Women")
        MEN = "men", _("Men")
        UNISEX = "unisex", _("Unisex")

    name = models.CharField(max_length=180)
    slug = models.SlugField(unique=True)
    sku = models.CharField(max_length=64, unique=True)
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT, related_name="watches")
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="watches",
    )
    collections = models.ManyToManyField(Collection, blank=True, related_name="watches")
    description = models.TextField()
    price = models.DecimalField(max_digits=12, decimal_places=2)
    discount_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    stock = models.PositiveIntegerField(default=0)
    movement = models.CharField(max_length=16, choices=Movement)
    case_material = models.CharField(max_length=80)
    case_diameter_mm = models.DecimalField(max_digits=4, decimal_places=1)
    strap_material = models.CharField(max_length=80)
    dial_color = models.CharField(max_length=80)
    water_resistance_m = models.PositiveSmallIntegerField()
    gender = models.CharField(max_length=10, choices=Gender, default=Gender.UNISEX)
    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["is_active", "-created_at"])]
        constraints = [
            models.CheckConstraint(
                condition=Q(price__gt=Decimal("0")),
                name="catalog_watch_price_positive",
            ),
            models.CheckConstraint(
                condition=(
                    Q(discount_price__isnull=True)
                    | (
                        Q(discount_price__gt=Decimal("0"))
                        & Q(discount_price__lt=models.F("price"))
                    )
                ),
                name="catalog_watch_discount_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.brand.name} {self.name}"

    def clean(self) -> None:
        super().clean()
        errors = {}
        if self.price is not None and self.price <= 0:
            errors["price"] = _("List price must be greater than zero.")
        if self.discount_price is not None:
            if self.discount_price <= 0:
                errors["discount_price"] = _(
                    "Discount price must be greater than zero."
                )
            elif self.price is not None and self.discount_price >= self.price:
                errors["discount_price"] = _(
                    "Discount price must be lower than the list price."
                )
        if errors:
            raise ValidationError(errors)

    @property
    def current_price(self) -> Decimal:
        return self.discount_price or self.price

    @property
    def primary_image(self):
        return next((image for image in self.images.all() if image.is_primary), None)


class WatchImage(models.Model):
    watch = models.ForeignKey(Watch, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="watches/%Y/%m/")
    alt_text = models.CharField(max_length=180, blank=True)
    position = models.PositiveSmallIntegerField(default=0)
    is_primary = models.BooleanField(default=False)

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["watch", "position"],
                name="catalog_watch_image_position_unique",
            ),
            models.UniqueConstraint(
                fields=["watch"],
                condition=Q(is_primary=True),
                name="catalog_one_primary_image_per_watch",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.watch} image {self.position + 1}"
