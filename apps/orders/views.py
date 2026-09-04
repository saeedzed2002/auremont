from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render

from apps.cart.services import find_cart_for_request

from .forms import CheckoutAddressForm, CouponForm
from .models import Order
from .services import (
    CheckoutValidationError,
    CouponValidationError,
    checkout_summary,
    create_paid_order,
)

CHECKOUT_ADDRESS_SESSION_KEY = "checkout_shipping_address"
CHECKOUT_COUPON_SESSION_KEY = "checkout_coupon_code"


@login_required
def checkout(request: HttpRequest) -> HttpResponse:
    cart = find_cart_for_request(request)
    try:
        checkout_summary(cart)
    except CheckoutValidationError as error:
        messages.error(request, str(error))
        return redirect("cart:detail")

    if request.method == "POST":
        form = CheckoutAddressForm(request.POST, user=request.user)
        if form.is_valid():
            request.session[CHECKOUT_ADDRESS_SESSION_KEY] = form.shipping_address()
            return redirect("orders:checkout_review")
    else:
        form = CheckoutAddressForm(user=request.user)

    return render(request, "orders/checkout.html", {"form": form})


@login_required
def checkout_review(request: HttpRequest) -> HttpResponse:
    shipping_address = _shipping_address_or_redirect(request)
    if shipping_address is None:
        return redirect("orders:checkout")

    try:
        summary = _summary_for_session_coupon(request)
    except CouponValidationError as error:
        request.session.pop(CHECKOUT_COUPON_SESSION_KEY, None)
        messages.error(request, str(error))
        try:
            summary = checkout_summary(find_cart_for_request(request))
        except CheckoutValidationError as cart_error:
            messages.error(request, str(cart_error))
            return redirect("cart:detail")
    except CheckoutValidationError as error:
        messages.error(request, str(error))
        return redirect("cart:detail")

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "remove_coupon":
            request.session.pop(CHECKOUT_COUPON_SESSION_KEY, None)
            messages.success(request, "Coupon removed from this checkout.")
        elif action == "apply_coupon":
            form = CouponForm(request.POST)
            if form.is_valid():
                try:
                    checkout_summary(
                        find_cart_for_request(request),
                        coupon_code=form.cleaned_data["code"],
                    )
                except CouponValidationError as error:
                    request.session.pop(CHECKOUT_COUPON_SESSION_KEY, None)
                    messages.error(request, str(error))
                else:
                    request.session[CHECKOUT_COUPON_SESSION_KEY] = form.cleaned_data[
                        "code"
                    ]
                    messages.success(request, "Coupon applied to this checkout.")
            else:
                messages.error(request, "Enter a valid coupon code.")
        else:
            return HttpResponseBadRequest("Unknown coupon action.")
        return redirect("orders:checkout_review")

    return render(
        request,
        "orders/review.html",
        {
            "coupon_form": CouponForm(
                initial={"code": summary.coupon.code if summary.coupon else ""}
            ),
            "shipping_address": shipping_address,
            "summary": summary,
        },
    )


@login_required
def mock_payment(request: HttpRequest) -> HttpResponse:
    shipping_address = _shipping_address_or_redirect(request)
    if shipping_address is None:
        return redirect("orders:checkout")

    try:
        summary = _summary_for_session_coupon(request)
    except CouponValidationError as error:
        request.session.pop(CHECKOUT_COUPON_SESSION_KEY, None)
        messages.error(request, str(error))
        return redirect("orders:checkout_review")
    except CheckoutValidationError as error:
        messages.error(request, str(error))
        return redirect("cart:detail")

    if request.method == "GET":
        return render(
            request,
            "orders/mock_payment.html",
            {"shipping_address": shipping_address, "summary": summary},
        )

    outcome = request.POST.get("outcome")
    if outcome == "failure":
        return render(
            request,
            "orders/payment_failed.html",
            {"shipping_address": shipping_address, "summary": summary},
        )
    if outcome != "success":
        return HttpResponseBadRequest("Unknown payment outcome.")

    try:
        order = create_paid_order(
            user=request.user,
            cart=find_cart_for_request(request),
            shipping_address=shipping_address,
            coupon_code=_coupon_code_from_session(request),
        )
    except CouponValidationError as error:
        request.session.pop(CHECKOUT_COUPON_SESSION_KEY, None)
        messages.error(request, str(error))
        return redirect("orders:checkout_review")
    except CheckoutValidationError as error:
        messages.error(request, str(error))
        return redirect("cart:detail")

    request.session.pop(CHECKOUT_ADDRESS_SESSION_KEY, None)
    request.session.pop(CHECKOUT_COUPON_SESSION_KEY, None)
    messages.success(request, f"Order {order.order_number} has been confirmed.")
    return redirect("orders:detail", order_number=order.order_number)


@login_required
def order_history(request: HttpRequest) -> HttpResponse:
    orders = Order.objects.filter(user=request.user).prefetch_related("items")
    return render(request, "orders/history.html", {"orders": orders})


@login_required
def order_detail(request: HttpRequest, order_number: str) -> HttpResponse:
    order = get_object_or_404(
        Order.objects.prefetch_related("items"),
        user=request.user,
        order_number=order_number,
    )
    return render(request, "orders/detail.html", {"order": order})


def _shipping_address_or_redirect(request: HttpRequest) -> dict[str, str] | None:
    shipping_address = request.session.get(CHECKOUT_ADDRESS_SESSION_KEY)
    if not isinstance(shipping_address, dict):
        messages.error(
            request, "Choose a delivery address before reviewing your order."
        )
        return None
    return shipping_address


def _coupon_code_from_session(request: HttpRequest) -> str | None:
    coupon_code = request.session.get(CHECKOUT_COUPON_SESSION_KEY)
    return coupon_code if isinstance(coupon_code, str) else None


def _summary_for_session_coupon(request: HttpRequest):
    return checkout_summary(
        find_cart_for_request(request),
        coupon_code=_coupon_code_from_session(request),
    )
