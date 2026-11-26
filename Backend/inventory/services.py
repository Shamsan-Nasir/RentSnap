
from collections import defaultdict
from datetime import date, timedelta

from django.db.models import Q
from django.utils import timezone

from rentals.models import Rental, RentalItem


def peak_committed_stock(
    product,
    start_date,
    end_date=None,
    *,
    today=None,
):
    if today is None:
        today = timezone.localdate()

    if end_date is None:
        end_date = date.max

    events = defaultdict(int)

    def add_period(start, end, quantity):
        start = max(start, start_date)
        end = min(end, end_date)

        if quantity <= 0 or start > end:
            return

        events[start] += quantity

        if end < end_date:
            events[end + timedelta(days=1)] -= quantity

    items = (
        RentalItem.objects
        .filter(product=product)
        .filter(
            Q(rental__status=Rental.Status.ACTIVE)
            |
            Q(
                rental__status__in=[
                    Rental.Status.BOOKED,
                    Rental.Status.COMPLETED,
                ],
                rental__end_date__gte=today,
            )
        )
        .select_related("rental")
    )

    for item in items:
        rental = item.rental

        outstanding = (
            item.quantity - item.returned_quantity
        )

        if rental.status == Rental.Status.ACTIVE:

            if rental.end_date < today:
                add_period(
                    today,
                    date.max,
                    outstanding,
                )

            else:
                add_period(
                    today,
                    rental.end_date,
                    item.quantity,
                )

                if rental.end_date < date.max:
                    add_period(
                        rental.end_date + timedelta(days=1),
                        date.max,
                        outstanding,
                    )

        else:
            add_period(
                rental.start_date,
                rental.end_date,
                item.quantity,
            )

    current = 0
    peak = 0

    for day in sorted(events):
        current += events[day]
        peak = max(peak, current)

    return peak


def minimum_required_stock(product):
    today = timezone.localdate()

    return peak_committed_stock(
        product,
        start_date=today,
        today=today,
    )


def available_quantity(
    product,
    start_date,
    end_date,
    *,
    today=None,
):
    committed = peak_committed_stock(
        product,
        start_date=start_date,
        end_date=end_date,
        today=today,
    )

    return max(
        0,
        product.total_quantity - committed,
    )
