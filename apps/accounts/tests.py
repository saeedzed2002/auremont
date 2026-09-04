from django.contrib.auth import get_user_model
from django.test import TestCase


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
