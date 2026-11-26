
from decimal import Decimal

from django.db.models import F, Sum

from inventory.models import Product
from payments.models import Payment
from rentals.models import Rental, RentalItem
from rentals.services import rental_days


def get_dashboard_summary(shop):

    total_products = Product.objects.filter(
        shop=shop,
    ).count()

    open_rentals = Rental.objects.filter(
        shop=shop,
        status__in=[
            Rental.Status.BOOKED,
            Rental.Status.ACTIVE,
        ],
    )

    active_rentals = open_rentals.filter(
        status=Rental.Status.ACTIVE,
    ).count()

    physically_outstanding = (
        RentalItem.objects
        .filter(
            rental__in=open_rentals,
            rental__status=Rental.Status.ACTIVE,
        )
        .aggregate(
            total=Sum(
                F("quantity") - F("returned_quantity"),
                default=0,
            )
        )["total"]
    )

    charge_rows = (
        RentalItem.objects
        .filter(rental__in=open_rentals)
        .values_list(
            "quantity",
            "daily_rate_snapshot",
            "rental__start_date",
            "rental__end_date",
        )
        .iterator(chunk_size=1000)
    )

    total_charge = sum(
        (
            quantity
            * daily_rate
            * rental_days(start_date, end_date)

            for quantity, daily_rate, start_date, end_date
            in charge_rows
        ),
        Decimal("0.00"),
    )

    payment_amounts = (
        Payment.objects
        .filter(rental__in=open_rentals)
        .values_list("amount", flat=True)
        .iterator(chunk_size=1000)
    )

    total_paid = sum(
        payment_amounts,
        Decimal("0.00"),
    )

    outstanding_receivables = (
        total_charge - total_paid
    )

    return {
        "total_products": total_products,
        "active_rentals": active_rentals,
        "physically_outstanding_units": physically_outstanding,
        "outstanding_receivables": format(
            outstanding_receivables,
            ".2f",
        ),
    }
