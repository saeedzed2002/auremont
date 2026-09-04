from decimal import Decimal

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from apps.catalog.models import Brand, Category, Watch

from .models import Cart, CartItem


class CartFactoryMixin:
    def create_watch(self, **overrides) -> Watch:
        brand = Brand.objects.create(name="Tudor", slug="tudor")
        category = Category.objects.create(name="Diving", slug="diving")
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


class CartModelTests(CartFactoryMixin, TestCase):
    def test_cart_requires_exactly_one_owner(self) -> None:
        with self.assertRaises(IntegrityError), transaction.atomic():
            Cart.objects.create()

        with self.assertRaises(IntegrityError), transaction.atomic():
            Cart.objects.create(session_key="")

        user = get_user_model().objects.create_user(
            email="collector@example.com",
            password="a-strong-test-password",
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            Cart.objects.create(user=user, session_key="guest-session")

    def test_cart_item_quantity_must_be_positive(self) -> None:
        cart = Cart.objects.create(session_key="guest-session")
        watch = self.create_watch()

        with self.assertRaises(IntegrityError), transaction.atomic():
            CartItem.objects.create(cart=cart, watch=watch, quantity=0)


class CartFlowTests(CartFactoryMixin, TestCase):
    password = "a-strong-test-password"

    def setUp(self) -> None:
        self.watch = self.create_watch(discount_price=Decimal("3995.00"))

    def add_to_cart(self, quantity: int, **data):
        payload = {"quantity": quantity, **data}
        return self.client.post(
            reverse("cart:add", kwargs={"slug": self.watch.slug}),
            payload,
        )

    def guest_cart(self) -> Cart:
        return Cart.objects.get(session_key=self.client.session.session_key)

    def test_guest_cart_survives_browsing_and_calculates_server_side_prices(
        self,
    ) -> None:
        response = self.add_to_cart(2, price="1.00")
        self.assertRedirects(
            response,
            reverse("catalog:watch_detail", kwargs={"slug": self.watch.slug}),
        )
        cart = self.guest_cart()
        self.assertEqual(cart.items.get().quantity, 2)

        self.client.get(reverse("core:home"))
        self.client.get(reverse("catalog:watch_list"))
        response = self.client.get(reverse("cart:detail"))

        self.assertEqual(response.context["summary"].item_count, 2)
        self.assertEqual(response.context["summary"].subtotal, Decimal("7990.00"))
        self.assertContains(response, "$3995.00 each")

    def test_add_and_update_reject_quantities_above_current_stock(self) -> None:
        self.add_to_cart(2)
        item = self.guest_cart().items.get()

        self.add_to_cart(2)
        item.refresh_from_db()
        self.assertEqual(item.quantity, 2)

        response = self.client.post(
            reverse("cart:update", kwargs={"pk": item.pk}), {"quantity": 4}
        )
        self.assertRedirects(response, reverse("cart:detail"))
        item.refresh_from_db()
        self.assertEqual(item.quantity, 2)

    def test_invalid_or_inactive_watches_cannot_be_added(self) -> None:
        response = self.add_to_cart(0)
        self.assertRedirects(
            response,
            reverse("catalog:watch_detail", kwargs={"slug": self.watch.slug}),
        )
        self.assertFalse(Cart.objects.exists())

        self.watch.is_active = False
        self.watch.save(update_fields=["is_active"])
        response = self.add_to_cart(1)
        self.assertEqual(response.status_code, 404)

    def test_cart_item_can_be_removed_with_post(self) -> None:
        self.add_to_cart(1)
        item = self.guest_cart().items.get()

        response = self.client.post(reverse("cart:remove", kwargs={"pk": item.pk}))

        self.assertRedirects(response, reverse("cart:detail"))
        self.assertFalse(CartItem.objects.filter(pk=item.pk).exists())

    def test_authenticated_customer_receives_a_persistent_cart(self) -> None:
        user = get_user_model().objects.create_user(
            email="collector@example.com",
            password=self.password,
        )
        self.client.force_login(user)

        self.add_to_cart(1)

        cart = Cart.objects.get(user=user)
        self.assertEqual(cart.items.get().watch, self.watch)

    def test_login_merges_guest_and_customer_carts_with_stock_limit(self) -> None:
        self.add_to_cart(2)
        guest_cart = self.guest_cart()
        user = get_user_model().objects.create_user(
            email="collector@example.com",
            password=self.password,
        )
        EmailAddress.objects.create(
            user=user,
            email=user.email,
            primary=True,
            verified=True,
        )
        user_cart = Cart.objects.create(user=user)
        CartItem.objects.create(cart=user_cart, watch=self.watch, quantity=2)

        response = self.client.post(
            reverse("account_login"),
            {"login": user.email, "password": self.password},
        )

        self.assertRedirects(response, reverse("accounts:dashboard"))
        user_cart.refresh_from_db()
        self.assertEqual(user_cart.items.get(watch=self.watch).quantity, 3)
        self.assertFalse(Cart.objects.filter(pk=guest_cart.pk).exists())

    def test_login_discards_unavailable_guest_items_during_cart_merge(self) -> None:
        self.add_to_cart(1)
        guest_cart = self.guest_cart()
        self.watch.stock = 0
        self.watch.save(update_fields=["stock", "updated_at"])
        user = get_user_model().objects.create_user(
            email="collector@example.com",
            password=self.password,
        )
        EmailAddress.objects.create(
            user=user,
            email=user.email,
            primary=True,
            verified=True,
        )

        response = self.client.post(
            reverse("account_login"),
            {"login": user.email, "password": self.password},
        )

        self.assertRedirects(response, reverse("accounts:dashboard"))
        self.assertFalse(Cart.objects.filter(pk=guest_cart.pk).exists())
        self.assertFalse(Cart.objects.get(user=user).items.exists())

    def test_add_uses_a_safe_return_url(self) -> None:
        response = self.add_to_cart(1, next="https://untrusted.example/cart")

        self.assertRedirects(
            response,
            reverse("catalog:watch_detail", kwargs={"slug": self.watch.slug}),
        )
