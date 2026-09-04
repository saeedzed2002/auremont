from decimal import Decimal
from io import StringIO

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from .models import Brand, Category, Watch, WatchImage


class CatalogFactoryMixin:
    def create_watch(self, **overrides) -> Watch:
        brand = overrides.pop(
            "brand",
            Brand.objects.get_or_create(name="Tudor", defaults={"slug": "tudor"})[0],
        )
        category = overrides.pop(
            "category",
            Category.objects.get_or_create(
                name="Diving",
                defaults={"slug": "diving"},
            )[0],
        )
        defaults = {
            "name": "Black Bay Fifty-Eight",
            "slug": "tudor-black-bay-fifty-eight",
            "sku": "TUD-BB58-001",
            "brand": brand,
            "category": category,
            "description": "A compact automatic diving watch.",
            "price": Decimal("4475.00"),
            "stock": 3,
            "movement": Watch.Movement.AUTOMATIC,
            "case_material": "Stainless steel",
            "case_diameter_mm": Decimal("39.0"),
            "strap_material": "Stainless steel bracelet",
            "dial_color": "Black",
            "water_resistance_m": 200,
        }
        defaults.update(overrides)
        return Watch.objects.create(**defaults)


class WatchModelTests(CatalogFactoryMixin, TestCase):
    def test_current_price_uses_discount_when_present(self) -> None:
        watch = self.create_watch(discount_price=Decimal("3995.00"))

        self.assertEqual(watch.current_price, Decimal("3995.00"))

    def test_discount_must_be_lower_than_list_price(self) -> None:
        watch = Watch(
            name="Invalid price watch",
            slug="invalid-price-watch",
            sku="TUD-INVALID-001",
            brand=Brand.objects.create(name="Omega", slug="omega"),
            category=Category.objects.create(name="Classic", slug="classic"),
            description="Validation test watch.",
            price=Decimal("100.00"),
            discount_price=Decimal("100.00"),
            stock=1,
            movement=Watch.Movement.AUTOMATIC,
            case_material="Steel",
            case_diameter_mm=Decimal("40.0"),
            strap_material="Leather",
            dial_color="Black",
            water_resistance_m=50,
        )

        with self.assertRaises(ValidationError):
            watch.full_clean()

    def test_price_must_be_greater_than_zero(self) -> None:
        watch = self.create_watch()
        watch.price = Decimal("0.00")

        with self.assertRaises(ValidationError):
            watch.full_clean()

    def test_only_one_primary_image_is_allowed_for_each_watch(self) -> None:
        watch = self.create_watch()
        primary_image = WatchImage.objects.create(
            watch=watch,
            image="watches/primary.jpg",
            position=0,
            is_primary=True,
        )

        self.assertEqual(watch.primary_image, primary_image)

        with self.assertRaises(IntegrityError), transaction.atomic():
            WatchImage.objects.create(
                watch=watch,
                image="watches/another-primary.jpg",
                position=1,
                is_primary=True,
            )


class CatalogViewTests(CatalogFactoryMixin, TestCase):
    def test_catalog_lists_only_active_watches(self) -> None:
        active_watch = self.create_watch()
        self.create_watch(
            name="Hidden watch",
            slug="hidden-watch",
            sku="TUD-HIDDEN-001",
            is_active=False,
        )

        response = self.client.get(reverse("catalog:watch_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, active_watch.name)
        self.assertNotContains(response, "Hidden watch")

    def test_active_watch_detail_is_public_and_inactive_watch_is_hidden(self) -> None:
        active_watch = self.create_watch()
        hidden_watch = self.create_watch(
            name="Hidden watch",
            slug="hidden-watch",
            sku="TUD-HIDDEN-001",
            is_active=False,
        )

        detail_response = self.client.get(
            reverse("catalog:watch_detail", kwargs={"slug": active_watch.slug})
        )
        hidden_response = self.client.get(
            reverse("catalog:watch_detail", kwargs={"slug": hidden_watch.slug})
        )

        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, "Specifications")
        self.assertEqual(hidden_response.status_code, 404)


class CatalogFixtureTests(TestCase):
    def test_demo_fixture_loads_valid_catalog_data(self) -> None:
        call_command("loaddata", "catalog_demo", stdout=StringIO())

        self.assertEqual(Watch.objects.count(), 3)
        self.assertEqual(Watch.objects.filter(is_active=True).count(), 3)
