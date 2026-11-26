
from decimal import Decimal

from django.db import transaction
from rest_framework.exceptions import ValidationError

from rentals.models import Rental

from rentals.services import (
    _get_locked_rental,
    calculate_outstanding_balance,
    load_rental_details,
)

from .models import Payment


@transaction.atomic
def record_payment(shop, rental_id, amount):
    rental = _get_locked_rental(
        shop,
        rental_id,
    )

    if rental.status not in [
        Rental.Status.BOOKED,
        Rental.Status.ACTIVE,
    ]:
        raise ValidationError({
            "detail": (
                "Payments can only be recorded "
                "for BOOKED or ACTIVE rentals."
            )
        })

    if amount <= Decimal("0.00"):
        raise ValidationError({
            "amount": (
                "Payment amount must be greater "
                "than zero."
            )
        })

    outstanding = calculate_outstanding_balance(
        rental
    )

    if amount > outstanding:
        raise ValidationError({
            "amount": (
                f"Payment exceeds the outstanding "
                f"balance of {outstanding:.2f} BDT."
            )
        })

    Payment.objects.create(
        rental=rental,
        amount=amount,
    )

    return load_rental_details(rental)

