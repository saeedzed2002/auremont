from .base import *  # noqa: F403
from .base import env

DEBUG = True
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
