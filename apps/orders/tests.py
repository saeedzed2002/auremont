from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Address
from apps.cart.models import Cart, CartItem
from apps.catalog.models import Brand, Category, Watch

from .models import Order
from .services import CheckoutValidationError, create_paid_order


class OrderFactoryMixin:
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

    def shipping_address(self) -> dict[str, str]:
        return {
            "full_name": "Auremont Collector",
            "phone": "+98 21 0000 0000",
            "province": "Tehran",
            "city": "Tehran",
            "postal_code": "1234567890",
            "address_line": "12 Watchmaker Lane",
        }


class OrderModelTests(OrderFactoryMixin, TestCase):
    def test_status_transitions_are_explicit(self) -> None:
        user = get_user_model().objects.create_user(
            email="collector@example.com",
            password="a-strong-test-password",
        )
        order = Order.objects.create(
            user=user,
            subtotal=Decimal("100.00"),
            total=Decimal("100.00"),
            shipping_full_name="Auremont Collector",
            shipping_phone="+98 21 0000 0000",
            shipping_province="Tehran",
            shipping_city="Tehran",
            shipping_postal_code="1234567890",
            shipping_address_line="12 Watchmaker Lane",
        )

        order.transition_to(Order.Status.PAID)
        self.assertEqual(order.status, Order.Status.PAID)

        with self.assertRaises(ValidationError):
            order.transition_to(Order.Status.SHIPPED)


class OrderServiceTests(OrderFactoryMixin, TestCase):
    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user(
            email="collector@example.com",
            password="a-strong-test-password",
        )
        self.watch = self.create_watch(discount_price=Decimal("3995.00"))
        self.cart = Cart.objects.create(user=self.user)
        self.cart_item = CartItem.objects.create(
            cart=self.cart,
            watch=self.watch,
            quantity=2,
        )

    def test_successful_order_snapshots_current_product_data_and_consumes_stock(
        self,
    ) -> None:
        order = create_paid_order(
            user=self.user,
            cart=self.cart,
            shipping_address=self.shipping_address(),
        )

        order_item = order.items.get()
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertEqual(order.subtotal, Decimal("7990.00"))
        self.assertEqual(order.total, Decimal("7990.00"))
        self.assertEqual(order_item.product_name, "Tudor Black Bay Fifty-Eight")
        self.assertEqual(order_item.sku, self.watch.sku)
        self.assertEqual(order_item.unit_price, Decimal("3995.00"))
        self.assertEqual(order_item.total_price, Decimal("7990.00"))
        self.assertFalse(CartItem.objects.filter(pk=self.cart_item.pk).exists())

        self.watch.refresh_from_db()
        self.assertEqual(self.watch.stock, 1)

        self.watch.price = Decimal("5000.00")
        self.watch.discount_price = None
        self.watch.name = "Changed catalog name"
        self.watch.save()
        order_item.refresh_from_db()
        self.assertEqual(order_item.product_name, "Tudor Black Bay Fifty-Eight")
        self.assertEqual(order_item.unit_price, Decimal("3995.00"))

    def test_insufficient_stock_rolls_back_order_creation_and_keeps_cart(self) -> None:
        self.watch.stock = 1
        self.watch.save(update_fields=["stock", "updated_at"])

        with self.assertRaises(CheckoutValidationError):
            create_paid_order(
                user=self.user,
                cart=self.cart,
                shipping_address=self.shipping_address(),
            )

        self.assertFalse(Order.objects.exists())
        self.assertTrue(CartItem.objects.filter(pk=self.cart_item.pk).exists())
        self.watch.refresh_from_db()
        self.assertEqual(self.watch.stock, 1)


class CheckoutFlowTests(OrderFactoryMixin, TestCase):
    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user(
            email="collector@example.com",
            password="a-strong-test-password",
        )
        self.watch = self.create_watch(stock=3)
        self.cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=self.cart, watch=self.watch, quantity=1)
        self.address = Address.objects.create(
            user=self.user,
            is_default=True,
            **self.shipping_address(),
        )

    def begin_saved_address_checkout(self) -> None:
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("orders:checkout"),
            {"saved_address": self.address.pk},
        )
        self.assertRedirects(response, reverse("orders:checkout_review"))

    def test_checkout_requires_authentication(self) -> None:
        response = self.client.get(reverse("orders:checkout"))

        self.assertRedirects(
            response,
            f"{reverse('account_login')}?next={reverse('orders:checkout')}",
        )

    def test_checkout_accepts_a_manual_delivery_address(self) -> None:
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("orders:checkout"),
            self.shipping_address(),
        )

        self.assertRedirects(response, reverse("orders:checkout_review"))
        review_response = self.client.get(reverse("orders:checkout_review"))
        self.assertContains(review_response, "Review your order")
        self.assertEqual(
            self.client.session["checkout_shipping_address"]["address_line"],
            "12 Watchmaker Lane",
        )

    def test_successful_mock_payment_creates_order_and_clears_cart(self) -> None:
        self.begin_saved_address_checkout()
        response = self.client.get(reverse("orders:mock_payment"))
        self.assertContains(response, "Demo payment")

        response = self.client.post(
            reverse("orders:mock_payment"),
            {"outcome": "success"},
        )

        order = Order.objects.get(user=self.user)
        self.assertRedirects(
            response,
            reverse("orders:detail", kwargs={"order_number": order.order_number}),
        )
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertFalse(self.cart.items.exists())
        self.watch.refresh_from_db()
        self.assertEqual(self.watch.stock, 2)
        self.assertNotIn("checkout_shipping_address", self.client.session)

    def test_failed_mock_payment_keeps_cart_and_stock_unchanged(self) -> None:
        self.begin_saved_address_checkout()

        response = self.client.post(
            reverse("orders:mock_payment"),
            {"outcome": "failure"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Payment not completed")
        self.assertFalse(Order.objects.exists())
        self.assertTrue(self.cart.items.exists())
        self.watch.refresh_from_db()
        self.assertEqual(self.watch.stock, 3)

    def test_order_detail_is_scoped_to_the_customer(self) -> None:
        order = create_paid_order(
            user=self.user,
            cart=self.cart,
            shipping_address=self.shipping_address(),
        )
        other_user = get_user_model().objects.create_user(
            email="other@example.com",
            password="a-strong-test-password",
        )
        self.client.force_login(other_user)

        response = self.client.get(
            reverse("orders:detail", kwargs={"order_number": order.order_number})
        )

        self.assertEqual(response.status_code, 404)
