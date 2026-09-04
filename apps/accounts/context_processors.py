from django.conf import settings


def authentication(request):
    return {"google_login_enabled": settings.GOOGLE_LOGIN_ENABLED}
