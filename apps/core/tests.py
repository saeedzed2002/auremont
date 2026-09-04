from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from .views import server_error


class HomePageTests(TestCase):
    def test_homepage_renders_the_storefront_shell(self) -> None:
        response = self.client.get(reverse("core:home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Time, Refined.")
        self.assertContains(response, "Featured watches")
        self.assertContains(response, "Independent demonstration project")

    def test_canonical_url_omits_search_parameters(self) -> None:
        response = self.client.get(reverse("catalog:search"), {"q": "tudor"})

        self.assertContains(
            response,
            '<link rel="canonical" href="http://testserver/search/">',
            html=True,
        )
        self.assertContains(
            response,
            '<meta property="og:type" content="website">',
            html=True,
        )


class ErrorPageTests(TestCase):
    @override_settings(DEBUG=False)
    def test_unknown_url_uses_the_branded_404_page(self) -> None:
        response = self.client.get("/this-page-does-not-exist/")

        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")
        self.assertContains(
            response,
            "This page is not part of the collection.",
            status_code=404,
        )

    def test_server_error_handler_returns_a_branded_500_page(self) -> None:
        request = RequestFactory().get("/service-error/")
        SessionMiddleware(lambda request: None).process_request(request)
        request.user = AnonymousUser()
        response = server_error(request)

        self.assertEqual(response.status_code, 500)
        self.assertContains(response, "The service needs a moment.", status_code=500)
