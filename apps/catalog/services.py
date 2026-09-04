from django.db import IntegrityError, transaction

from apps.orders.models import Order, OrderItem

from .models import Review, Watch


class ReviewValidationError(Exception):
    pass


PURCHASED_ORDER_STATUSES = (
    Order.Status.PAID,
    Order.Status.PROCESSING,
    Order.Status.SHIPPED,
    Order.Status.DELIVERED,
)


def has_verified_purchase(user, watch: Watch) -> bool:
    return OrderItem.objects.filter(
        order__user=user,
        order__status__in=PURCHASED_ORDER_STATUSES,
        watch=watch,
    ).exists()


def create_verified_review(*, user, watch: Watch, rating: int, comment: str) -> Review:
    if not has_verified_purchase(user, watch):
        raise ReviewValidationError(
            "Only customers who purchased this watch can leave a review."
        )

    try:
        with transaction.atomic():
            return Review.objects.create(
                user=user,
                watch=watch,
                rating=rating,
                comment=comment,
                is_verified_purchase=True,
            )
    except IntegrityError as error:
        raise ReviewValidationError("You have already reviewed this watch.") from error
