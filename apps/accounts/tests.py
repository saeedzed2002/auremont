from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Address


class UserModelTests(TestCase):
    def test_create_user_uses_email_as_the_login_identifier(self) -> None:
        user = get_user_model().objects.create_user(
            email="collector@example.com",
            password="not-a-real-password",
            full_name="Auremont Collector",
        )

        self.assertEqual(user.email, "collector@example.com")
        self.assertEqual(user.full_name, "Auremont Collector")
        self.assertTrue(user.check_password("not-a-real-password"))
        self.assertEqual(user.get_username(), "collector@example.com")

    def test_create_user_requires_email(self) -> None:
        with self.assertRaisesMessage(ValueError, "An email address is required."):
            get_user_model().objects.create_user(
                email="", password="not-a-real-password"
            )


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AccountFlowTests(TestCase):
    password = "a-strong-test-password"

    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user(
            email="collector@example.com",
            password=self.password,
            full_name="Auremont Collector",
        )
        EmailAddress.objects.create(
            user=self.user,
            email=self.user.email,
            primary=True,
            verified=True,
        )

    def sign_in(self) -> None:
        self.client.force_login(self.user)

    def address_data(self, **overrides) -> dict[str, str]:
        data = {
            "full_name": "Auremont Collector",
            "phone": "+98 21 0000 0000",
            "province": "Tehran",
            "city": "Tehran",
            "postal_code": "1234567890",
            "address_line": "12 Watchmaker Lane",
        }
        data.update(overrides)
        return data

    def test_signup_creates_a_user_with_the_supplied_full_name(self) -> None:
        response = self.client.post(
            reverse("account_signup"),
            {
                "full_name": "New Collector",
                "email": "new@example.com",
                "password1": self.password,
                "password2": self.password,
            },
        )

        self.assertRedirects(response, reverse("account_email_verification_sent"))
        user = get_user_model().objects.get(email="new@example.com")
        self.assertEqual(user.full_name, "New Collector")
        self.assertEqual(len(mail.outbox), 1)

    def test_verified_user_can_sign_in_and_sign_out_with_post(self) -> None:
        response = self.client.post(
            reverse("account_login"),
            {"login": self.user.email, "password": self.password},
        )

        self.assertRedirects(response, reverse("accounts:dashboard"))
        self.assertEqual(
            self.client.get(reverse("accounts:dashboard")).status_code, 200
        )

        response = self.client.post(reverse("account_logout"))

        self.assertRedirects(response, reverse("core:home"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_password_reset_sends_a_link_without_disclosing_the_account(self) -> None:
        response = self.client.post(
            reverse("account_reset_password"), {"email": self.user.email}
        )

        self.assertRedirects(response, reverse("account_reset_password_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("http://testserver", mail.outbox[0].body)

    def test_first_address_becomes_default_and_new_default_replaces_it(self) -> None:
        self.sign_in()

        response = self.client.post(
            reverse("accounts:address_create"), self.address_data()
        )
        self.assertRedirects(response, reverse("accounts:address_list"))
        first_address = Address.objects.get(user=self.user)
        self.assertTrue(first_address.is_default)

        response = self.client.post(
            reverse("accounts:address_create"),
            self.address_data(
                full_name="Second Recipient",
                city="Shiraz",
                postal_code="9876543210",
                is_default="on",
            ),
        )
        self.assertRedirects(response, reverse("accounts:address_list"))

        first_address.refresh_from_db()
        second_address = Address.objects.get(full_name="Second Recipient")
        self.assertFalse(first_address.is_default)
        self.assertTrue(second_address.is_default)

    def test_address_management_is_scoped_to_the_authenticated_user(self) -> None:
        other_user = get_user_model().objects.create_user(
            email="other@example.com",
            password=self.password,
        )
        other_address = Address.objects.create(
            user=other_user,
            full_name="Other Collector",
            phone="+98 21 1111 1111",
            province="Tehran",
            city="Tehran",
            postal_code="1111111111",
            address_line="1 Other Street",
            is_default=True,
        )
        self.sign_in()

        response = self.client.get(
            reverse("accounts:address_update", args=[other_address.pk])
        )

        self.assertEqual(response.status_code, 404)

    def test_deleting_the_default_address_promotes_an_available_address(self) -> None:
        self.sign_in()
        first_address = Address.objects.create(
            user=self.user,
            full_name="First Recipient",
            phone="+98 21 0000 0000",
            province="Tehran",
            city="Tehran",
            postal_code="1234567890",
            address_line="12 Watchmaker Lane",
            is_default=True,
        )
        replacement = Address.objects.create(
            user=self.user,
            full_name="Second Recipient",
            phone="+98 21 0000 0000",
            province="Fars",
            city="Shiraz",
            postal_code="9876543210",
            address_line="18 Watchmaker Lane",
        )

        response = self.client.post(
            reverse("accounts:address_delete", args=[first_address.pk])
        )

        self.assertRedirects(response, reverse("accounts:address_list"))
        replacement.refresh_from_db()
        self.assertTrue(replacement.is_default)
