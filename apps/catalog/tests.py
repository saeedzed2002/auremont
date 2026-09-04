from decimal import Decimal
from io import StringIO

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.orders.models import Order, OrderItem

from .models import Brand, Category, Collection, Review, Watch, WatchImage
from .views import CATALOG_PAGE_SIZE


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

    def test_catalog_filters_by_effective_price_and_sorts_results(self) -> None:
        sale_watch = self.create_watch(discount_price=Decimal("3995.00"))
        self.create_watch(
            name="Pelagos",
            slug="tudor-pelagos",
            sku="TUD-PEL-001",
            price=Decimal("6500.00"),
        )
        seiko = Brand.objects.create(name="Seiko", slug="seiko")
        self.create_watch(
            name="Presage",
            slug="seiko-presage",
            sku="SEI-PRE-001",
            brand=seiko,
            movement=Watch.Movement.QUARTZ,
            price=Decimal("495.00"),
        )

        response = self.client.get(
            reverse("catalog:watch_list"),
            {
                "brand": "tudor",
                "movement": Watch.Movement.AUTOMATIC,
                "max_price": "4000",
                "sort": "price_asc",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["page_obj"].object_list), [sale_watch])

    def test_search_matches_collections_and_hides_inactive_watches(self) -> None:
        watch = self.create_watch()
        collection = Collection.objects.create(
            name="Diving Watches",
            slug="diving-watches",
        )
        watch.collections.add(collection)
        self.create_watch(
            name="Hidden diver",
            slug="hidden-diver",
            sku="TUD-HIDDEN-002",
            description="A diving watch that is not public.",
            is_active=False,
        )

        response = self.client.get(reverse("catalog:search"), {"q": "Diving Watches"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, watch.name)
        self.assertNotContains(response, "Hidden diver")

    def test_catalog_paginates_large_result_sets(self) -> None:
        for number in range(CATALOG_PAGE_SIZE + 1):
            self.create_watch(
                name=f"Watch {number}",
                slug=f"watch-{number}",
                sku=f"TUD-PAGE-{number:03}",
            )

        response = self.client.get(reverse("catalog:watch_list"), {"page": "2"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page_obj"].number, 2)
        self.assertEqual(len(response.context["page_obj"].object_list), 1)

    def test_brand_page_lists_its_active_watches(self) -> None:
        watch = self.create_watch()

        response = self.client.get(
            reverse("catalog:brand_detail", kwargs={"slug": watch.brand.slug})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, watch.name)


class ReviewFlowTests(CatalogFactoryMixin, TestCase):
    password = "a-strong-test-password"

    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email="collector@example.com",
            password=self.password,
            full_name="Auremont Collector",
        )
        self.watch = self.create_watch()

    def create_order(self, *, status: str = Order.Status.PAID) -> Order:
        order = Order.objects.create(
            user=self.user,
            status=status,
            subtotal=self.watch.current_price,
            total=self.watch.current_price,
            shipping_full_name="Auremont Collector",
            shipping_phone="+98 21 0000 0000",
            shipping_province="Tehran",
            shipping_city="Tehran",
            shipping_postal_code="1234567890",
            shipping_address_line="12 Watchmaker Lane",
        )
        OrderItem.objects.create(
            order=order,
            watch=self.watch,
            product_name=str(self.watch),
            sku=self.watch.sku,
            unit_price=self.watch.current_price,
            quantity=1,
            total_price=self.watch.current_price,
        )
        return order

    def submit_review(self, **data):
        payload = {
            "rating": "5",
            "comment": "A precise, comfortable watch with excellent proportions.",
        }
        payload.update(data)
        return self.client.post(
            reverse("catalog:review_create", kwargs={"slug": self.watch.slug}),
            payload,
        )

    def test_review_submission_requires_authentication(self) -> None:
        response = self.submit_review()

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Review.objects.exists())

    def test_only_customer_with_a_paid_order_can_submit_a_verified_review(self) -> None:
        self.client.force_login(self.user)

        response = self.submit_review()

        self.assertRedirects(
            response,
            reverse("catalog:watch_detail", kwargs={"slug": self.watch.slug}),
        )
        self.assertFalse(Review.objects.exists())

        self.create_order()
        response = self.submit_review()

        self.assertRedirects(
            response,
            reverse("catalog:watch_detail", kwargs={"slug": self.watch.slug}),
        )
        review = Review.objects.get(user=self.user, watch=self.watch)
        self.assertTrue(review.is_verified_purchase)
        self.assertEqual(review.moderation_status, Review.ModerationStatus.PENDING)

    def test_cancelled_order_does_not_qualify_for_a_verified_review(self) -> None:
        self.create_order(status=Order.Status.CANCELLED)
        self.client.force_login(self.user)

        response = self.submit_review()

        self.assertRedirects(
            response,
            reverse("catalog:watch_detail", kwargs={"slug": self.watch.slug}),
        )
        self.assertFalse(Review.objects.exists())

    def test_pending_review_is_private_until_staff_approves_it(self) -> None:
        self.create_order()
        self.client.force_login(self.user)
        self.submit_review(comment="An excellent review visible only after approval.")
        review = Review.objects.get(user=self.user, watch=self.watch)

        self.client.logout()
        pending_response = self.client.get(
            reverse("catalog:watch_detail", kwargs={"slug": self.watch.slug})
        )
        self.assertNotContains(
            pending_response,
            "An excellent review visible only after approval.",
        )

        review.moderation_status = Review.ModerationStatus.APPROVED
        review.save(update_fields=["moderation_status", "updated_at"])
        approved_response = self.client.get(
            reverse("catalog:watch_detail", kwargs={"slug": self.watch.slug})
        )

        self.assertContains(
            approved_response,
            "An excellent review visible only after approval.",
        )
        self.assertContains(approved_response, "5.0/5")
        self.assertContains(approved_response, "Verified purchase")

    def test_customer_cannot_submit_a_second_review_for_the_same_watch(self) -> None:
        self.create_order()
        self.client.force_login(self.user)
        self.submit_review()

        response = self.submit_review(comment="A second review should not be stored.")

        self.assertRedirects(
            response,
            reverse("catalog:watch_detail", kwargs={"slug": self.watch.slug}),
        )
        self.assertEqual(
            Review.objects.filter(user=self.user, watch=self.watch).count(), 1
        )


class ReviewModelTests(CatalogFactoryMixin, TestCase):
    def test_review_database_constraints_protect_rating_and_uniqueness(self) -> None:
        user = User.objects.create_user(
            email="collector@example.com",
            password="a-strong-test-password",
        )
        watch = self.create_watch()
        Review.objects.create(
            user=user,
            watch=watch,
            rating=5,
            comment="A verified review created for database constraint coverage.",
            is_verified_purchase=True,
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            Review.objects.create(
                user=user,
                watch=watch,
                rating=5,
                comment="Duplicate review.",
                is_verified_purchase=True,
            )

        review = Review.objects.get(user=user, watch=watch)
        review.rating = 0
        with self.assertRaises(IntegrityError), transaction.atomic():
            review.save(update_fields=["rating"])


class CatalogFixtureTests(TestCase):
    def test_demo_fixture_loads_valid_catalog_data(self) -> None:
        call_command("loaddata", "catalog_demo", stdout=StringIO())

        self.assertEqual(Watch.objects.count(), 3)
        self.assertEqual(Watch.objects.filter(is_active=True).count(), 3)


class CatalogAdminTests(TestCase):
    def test_admin_can_create_a_watch_with_an_inline_image(self) -> None:
        administrator = User.objects.create_superuser(
            email="admin@example.com",
            password="secure-admin-password",
        )
        brand = Brand.objects.create(name="Cartier", slug="cartier")
        category = Category.objects.create(name="Classic", slug="classic")
        collection = Collection.objects.create(
            name="Editor's Selection",
            slug="editors-selection",
        )
        image = SimpleUploadedFile(
            "tank.png",
            (
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
                b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
                b"\x00\x00\x00\x0dIDATx\x9cc\xf8\xcf\xc0\xf0\x1f\x00\x05\x00"
                b"\x01\xff\x89\x99=\x1d\x00\x00\x00\x00IEND\xaeB`\x82"
            ),
            content_type="image/png",
        )
        self.client.force_login(administrator)

        with self.settings(
            STORAGES={
                "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
                "staticfiles": {
                    "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
                },
            }
        ):
            response = self.client.post(
                reverse("admin:catalog_watch_add"),
                data={
                    "name": "Tank Must",
                    "slug": "cartier-tank-must",
                    "sku": "CAR-TANK-001",
                    "brand": brand.pk,
                    "category": category.pk,
                    "collections": [collection.pk],
                    "description": "A compact quartz dress watch.",
                    "price": "3450.00",
                    "discount_price": "",
                    "stock": "2",
                    "movement": Watch.Movement.QUARTZ,
                    "case_material": "Stainless steel",
                    "case_diameter_mm": "33.7",
                    "strap_material": "Leather",
                    "dial_color": "Silver",
                    "water_resistance_m": "30",
                    "gender": Watch.Gender.UNISEX,
                    "is_active": "on",
                    "images-TOTAL_FORMS": "1",
                    "images-INITIAL_FORMS": "0",
                    "images-MIN_NUM_FORMS": "0",
                    "images-MAX_NUM_FORMS": "1000",
                    "images-0-image": image,
                    "images-0-alt_text": "Cartier Tank Must front view",
                    "images-0-position": "0",
                    "images-0-is_primary": "on",
                },
            )

        watch = Watch.objects.get(slug="cartier-tank-must")
        self.assertRedirects(response, reverse("admin:catalog_watch_changelist"))
        self.assertEqual(watch.images.count(), 1)
        self.assertTrue(watch.primary_image.is_primary)
