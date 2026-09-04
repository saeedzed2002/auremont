from allauth.account.adapter import DefaultAccountAdapter
from django.contrib import messages


class AuremontAccountAdapter(DefaultAccountAdapter):
    def login(self, request, user) -> None:
        from apps.cart.services import merge_session_cart_into_user_cart

        result = merge_session_cart_into_user_cart(request, user)
        if result.has_adjustments:
            messages.warning(
                request,
                (
                    "Your cart was merged. Unavailable quantities were adjusted "
                    "to current stock."
                ),
            )
        super().login(request, user)
