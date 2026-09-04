from datetime import timedelta
from decimal import Decimal
from threading import Barrier, Lock, Thread

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Address
from apps.cart.models import Cart, CartItem
from apps.catalog.models import Brand, Category, Watch

from .models import Coupon, Order
from .services import (
    CheckoutValidationError,
    CouponValidationError,
    checkout_summary,
    create_paid_order,
)


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


class CouponModelTests(TestCase):
    def test_coupon_normalizes_its_code_and_calculates_percentage_discount(
        self,
    ) -> None:
        coupon = Coupon.objects.create(
            code=" autumn10 ",
            discount_type=Coupon.DiscountType.PERCENTAGE,
            value=Decimal("10.00"),
        )

        self.assertEqual(coupon.code, "AUTUMN10")
        self.assertEqual(coupon.discount_for(Decimal("7990.00")), Decimal("799.00"))

    def test_coupon_rejects_invalid_percentage_and_validity_window(self) -> None:
        current_time = timezone.now()
        coupon = Coupon(
            code="INVALID",
            discount_type=Coupon.DiscountType.PERCENTAGE,
            value=Decimal("101.00"),
            valid_from=current_time,
            valid_until=current_time,
        )

        with self.assertRaises(ValidationError):
            coupon.full_clean()


class CouponServiceTests(OrderFactoryMixin, TestCase):
    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user(
            email="collector@example.com",
            password="a-strong-test-password",
        )
        self.watch = self.create_watch(discount_price=Decimal("3995.00"))
        self.cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=self.cart, watch=self.watch, quantity=2)

    def test_percentage_coupon_recalculates_server_total_and_is_snapshotted(
        self,
    ) -> None:
        coupon = Coupon.objects.create(
            code="autumn10",
            discount_type=Coupon.DiscountType.PERCENTAGE,
            value=Decimal("10.00"),
        )

        summary = checkout_summary(self.cart, coupon_code=" autumn10 ")
        order = create_paid_order(
            user=self.user,
            cart=self.cart,
            shipping_address=self.shipping_address(),
            coupon_code=coupon.code,
        )

        self.assertEqual(summary.discount, Decimal("799.00"))
        self.assertEqual(summary.total, Decimal("7191.00"))
        self.assertEqual(order.coupon_code, "AUTUMN10")
        self.assertEqual(order.discount, Decimal("799.00"))
        self.assertEqual(order.total, Decimal("7191.00"))

        coupon.value = Decimal("50.00")
        coupon.save(update_fields=["value", "updated_at"])
        order.refresh_from_db()
        self.assertEqual(order.discount, Decimal("799.00"))

    def test_fixed_coupon_reduces_the_server_calculated_total(self) -> None:
        Coupon.objects.create(
            code="COLLECTOR500",
            discount_type=Coupon.DiscountType.FIXED,
            value=Decimal("500.00"),
        )

        summary = checkout_summary(self.cart, coupon_code="collector500")

        self.assertEqual(summary.discount, Decimal("500.00"))
        self.assertEqual(summary.total, Decimal("7490.00"))

    def test_coupon_rejects_expiry_and_unmet_minimum_order(self) -> None:
        Coupon.objects.create(
            code="EXPIRED",
            discount_type=Coupon.DiscountType.FIXED,
            value=Decimal("100.00"),
            valid_until=timezone.now() - timedelta(seconds=1),
        )
        Coupon.objects.create(
            code="MINIMUM",
            discount_type=Coupon.DiscountType.FIXED,
            value=Decimal("100.00"),
            minimum_order=Decimal("8000.00"),
        )

        with self.assertRaises(CouponValidationError):
            checkout_summary(self.cart, coupon_code="EXPIRED")
        with self.assertRaises(CouponValidationError):
            checkout_summary(self.cart, coupon_code="MINIMUM")

    def test_coupon_rejects_inactive_and_not_yet_valid_codes(self) -> None:
        Coupon.objects.create(
            code="INACTIVE",
            discount_type=Coupon.DiscountType.FIXED,
            value=Decimal("100.00"),
            is_active=False,
        )
        Coupon.objects.create(
            code="FUTURE",
            discount_type=Coupon.DiscountType.FIXED,
            value=Decimal("100.00"),
            valid_from=timezone.now() + timedelta(minutes=1),
        )

        with self.assertRaises(CouponValidationError):
            checkout_summary(self.cart, coupon_code="INACTIVE")
        with self.assertRaises(CouponValidationError):
            checkout_summary(self.cart, coupon_code="FUTURE")

    def test_fixed_coupon_cannot_reduce_the_total_below_zero(self) -> None:
        Coupon.objects.create(
            code="FULLVALUE",
            discount_type=Coupon.DiscountType.FIXED,
            value=Decimal("10000.00"),
        )

        summary = checkout_summary(self.cart, coupon_code="FULLVALUE")

        self.assertEqual(summary.discount, Decimal("7990.00"))
        self.assertEqual(summary.total, Decimal("0.00"))


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

    def test_invalid_coupon_rolls_back_order_creation_and_keeps_cart(self) -> None:
        Coupon.objects.create(
            code="INACTIVE",
            discount_type=Coupon.DiscountType.FIXED,
            value=Decimal("100.00"),
            is_active=False,
        )

        with self.assertRaises(CouponValidationError):
            create_paid_order(
                user=self.user,
                cart=self.cart,
                shipping_address=self.shipping_address(),
                coupon_code="INACTIVE",
            )

        self.assertFalse(Order.objects.exists())
        self.assertTrue(CartItem.objects.filter(pk=self.cart_item.pk).exists())
        self.watch.refresh_from_db()
        self.assertEqual(self.watch.stock, 3)

    def test_order_cannot_be_created_from_another_customers_cart(self) -> None:
        other_user = get_user_model().objects.create_user(
            email="other@example.com",
            password="a-strong-test-password",
        )

        with self.assertRaises(CheckoutValidationError):
            create_paid_order(
                user=other_user,
                cart=self.cart,
                shipping_address=self.shipping_address(),
            )

        self.assertFalse(Order.objects.exists())
        self.assertTrue(CartItem.objects.filter(pk=self.cart_item.pk).exists())
        self.watch.refresh_from_db()
        self.assertEqual(self.watch.stock, 3)


class TransactionalStockReservationTests(OrderFactoryMixin, TransactionTestCase):
    password = "a-strong-test-password"

    def setUp(self) -> None:
        self.watch = self.create_watch(stock=1)
        self.users = [
            get_user_model().objects.create_user(
                email=f"collector-{index}@example.com",
                password=self.password,
            )
            for index in range(2)
        ]
        self.carts = [Cart.objects.create(user=user) for user in self.users]
        for cart in self.carts:
            CartItem.objects.create(cart=cart, watch=self.watch, quantity=1)

    def test_simultaneous_checkouts_allocate_stock_to_only_one_customer(self) -> None:
        barrier = Barrier(2)
        result_lock = Lock()
        results = []
        unexpected_errors = []

        def checkout(user_id: int, cart_id: int) -> None:
            close_old_connections()
            try:
                barrier.wait()
                user = get_user_model().objects.get(pk=user_id)
                cart = Cart.objects.get(pk=cart_id)
                create_paid_order(
                    user=user,
                    cart=cart,
                    shipping_address=self.shipping_address(),
                )
            except CheckoutValidationError:
                result = "rejected"
            except Exception as error:  # pragma: no cover - assertion below records it
                with result_lock:
                    unexpected_errors.append(repr(error))
                return
            else:
                result = "paid"
            finally:
                close_old_connections()

            with result_lock:
                results.append(result)

        threads = [
            Thread(target=checkout, args=(user.pk, cart.pk))
            for user, cart in zip(self.users, self.carts, strict=True)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(unexpected_errors, [])
        self.assertCountEqual(results, ["paid", "rejected"])
        self.assertEqual(Order.objects.count(), 1)
        self.watch.refresh_from_db()
        self.assertEqual(self.watch.stock, 0)
        self.assertEqual(CartItem.objects.count(), 1)


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

    def create_coupon(self, **overrides) -> Coupon:
        defaults = {
            "code": "AUTUMN10",
            "discount_type": Coupon.DiscountType.PERCENTAGE,
            "value": Decimal("10.00"),
        }
        defaults.update(overrides)
        return Coupon.objects.create(**defaults)

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

    def test_unknown_mock_payment_outcome_returns_a_bad_request(self) -> None:
        self.begin_saved_address_checkout()

        response = self.client.post(
            reverse("orders:mock_payment"),
            {"outcome": "unexpected"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Order.objects.exists())
        self.assertTrue(self.cart.items.exists())

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

    def test_successful_payment_revalidates_and_snapshots_an_applied_coupon(
        self,
    ) -> None:
        coupon = self.create_coupon()
        self.begin_saved_address_checkout()

        response = self.client.post(
            reverse("orders:checkout_review"),
            {"action": "apply_coupon", "code": " autumn10 "},
        )

        self.assertRedirects(response, reverse("orders:checkout_review"))
        review_response = self.client.get(reverse("orders:checkout_review"))
        self.assertEqual(review_response.context["summary"].coupon, coupon)
        self.assertEqual(review_response.context["summary"].discount, Decimal("447.50"))

        response = self.client.post(
            reverse("orders:mock_payment"),
            {"outcome": "success"},
        )

        order = Order.objects.get(user=self.user)
        self.assertRedirects(
            response,
            reverse("orders:detail", kwargs={"order_number": order.order_number}),
        )
        self.assertEqual(order.coupon_code, "AUTUMN10")
        self.assertEqual(order.discount, Decimal("447.50"))
        self.assertEqual(order.total, Decimal("4027.50"))

    def test_payment_rejects_a_coupon_that_becomes_invalid_after_review(self) -> None:
        coupon = self.create_coupon()
        self.begin_saved_address_checkout()
        self.client.post(
            reverse("orders:checkout_review"),
            {"action": "apply_coupon", "code": coupon.code},
        )
        coupon.is_active = False
        coupon.save(update_fields=["is_active", "updated_at"])

        response = self.client.post(
            reverse("orders:mock_payment"),
            {"outcome": "success"},
        )

        self.assertRedirects(response, reverse("orders:checkout_review"))
        self.assertFalse(Order.objects.exists())
        self.assertTrue(self.cart.items.exists())
        self.watch.refresh_from_db()
        self.assertEqual(self.watch.stock, 3)
        self.assertNotIn("checkout_coupon_code", self.client.session)
