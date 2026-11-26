
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from inventory.models import Product
from inventory.services import available_quantity

from .models import Customer, Rental, RentalItem


def rental_days(start_date, end_date):
    return (end_date - start_date).days + 1


def validate_booking_dates(start_date, end_date):
    today = timezone.localdate()

    if start_date < today:
        raise ValidationError({
            "start_date": "Rental cannot start in the past."
        })

    if end_date < start_date:
        raise ValidationError({
            "end_date": (
                "End date cannot be before start date."
            )
        })

    if rental_days(start_date, end_date) > 30:
        raise ValidationError({
            "end_date": (
                "Rental duration cannot exceed 30 days."
            )
        })

    return today


def calculate_rental_total(rental):
    days = rental_days(
        rental.start_date,
        rental.end_date,
    )

    return sum(
        (
            item.quantity
            * item.daily_rate_snapshot
            * days
            for item in rental.items.all()
        ),
        Decimal("0.00"),
    )


@transaction.atomic
def create_rental(
    shop,
    customer_id,
    start_date,
    end_date,
    items,
):
    today = validate_booking_dates(
        start_date,
        end_date,
    )

    if not items:
        raise ValidationError({
            "items": "At least one product is required."
        })

    if any(item["quantity"] <= 0 for item in items):
        raise ValidationError({
            "items": "Quantities must be positive."
        })

    product_ids = [
        item["product_id"]
        for item in items
    ]

    if len(product_ids) != len(set(product_ids)):
        raise ValidationError({
            "items": (
                "The same product cannot appear twice."
            )
        })

    customer = Customer.objects.filter(
        pk=customer_id,
        shop=shop,
    ).first()

    if customer is None:
        raise ValidationError({
            "customer_id": "Invalid customer."
        })

    products = list(
        Product.objects
        .select_for_update()
        .filter(
            pk__in=product_ids,
            shop=shop,
        )
        .order_by("pk")
    )

    if len(products) != len(product_ids):
        raise ValidationError({
            "items": (
                "One or more products are invalid."
            )
        })

    products_by_id = {
        product.pk: product
        for product in products
    }

    rental_items = []

    for item in items:
        product = products_by_id[item["product_id"]]
        quantity = item["quantity"]

        if not product.is_active:
            raise ValidationError({
                "items": (
                    f"{product.name} is inactive."
                )
            })

        available = available_quantity(
            product=product,
            start_date=start_date,
            end_date=end_date,
            today=today,
        )

        if quantity > available:
            raise ValidationError({
                "items": (
                    f"Insufficient stock for {product.name}. "
                    f"Requested: {quantity}. "
                    f"Available: {available}."
                )
            })

        rental_items.append(
            RentalItem(
                product=product,
                quantity=quantity,
                returned_quantity=0,
                daily_rate_snapshot=product.daily_rate,
            )
        )

    rental = Rental.objects.create(
        shop=shop,
        customer=customer,
        start_date=start_date,
        end_date=end_date,
        status=Rental.Status.BOOKED,
    )

    for item in rental_items:
        item.rental = rental

    RentalItem.objects.bulk_create(rental_items)

    return rental
