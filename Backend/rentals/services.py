
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
   
from inventory.models import Product
from .models import Customer, Rental, RentalItem

from rest_framework.exceptions import (
    NotFound,
    ValidationError,
)

from inventory.services import (
    available_quantity,
    physically_outstanding_by_product,
)

from django.db.models import (
    Prefetch,
    prefetch_related_objects,
)

from payments.models import Payment



def rental_detail_prefetches():
    return (
        Prefetch(
            "items",
            queryset=(
                RentalItem.objects
                .select_related("product")
                .order_by("pk")
            ),
        ),
        Prefetch(
            "payments",
            queryset=(
                Payment.objects
                .order_by("created_at", "pk")
            ),
        ),
    )


def load_rental_details(rental):
    prefetch_related_objects(
        [rental],
        *rental_detail_prefetches(),
    )

    return rental


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


def _get_locked_rental(shop, rental_id):
    rental = (
        Rental.objects
        .select_for_update()
        .filter(
            pk=rental_id,
            shop=shop,
        )
        .first()
    )

    if rental is None:
        raise NotFound("Rental not found.")

    return rental


def _get_items_and_lock_products(rental):
    items = list(
        rental.items.order_by("pk")
    )

    if not items:
        raise ValidationError({
            "detail": "Rental has no items."
        })

    product_ids = [
        item.product_id
        for item in items
    ]

    products = list(
        Product.objects
        .select_for_update()
        .filter(
            shop_id=rental.shop_id,
            pk__in=product_ids,
        )
        .order_by("pk")
    )

    if len(products) != len(set(product_ids)):
        raise ValidationError({
            "detail": "Rental contains invalid products."
        })

    products_by_id = {
        product.pk: product
        for product in products
    }

    return items, products_by_id



@transaction.atomic
def dispatch_rental(shop, rental_id):
    rental = _get_locked_rental(
        shop,
        rental_id,
    )

    if rental.status != Rental.Status.BOOKED:
        raise ValidationError({
            "detail": (
                "Only a BOOKED rental can be dispatched."
            )
        })

    items, products_by_id = (
        _get_items_and_lock_products(rental)
    )

    today = timezone.localdate()

    if not (
        rental.start_date <= today <= rental.end_date
    ):
        raise ValidationError({
            "detail": (
                "Dispatch must occur within "
                "the booked rental dates."
            )
        })

    outstanding_by_product = (
        physically_outstanding_by_product(
            shop,
            products_by_id.keys(),
        )
    )

    for item in items:
        product = products_by_id[item.product_id]

        if item.returned_quantity != 0:
            raise ValidationError({
                "detail": (
                    "Undispatched rental contains "
                    "invalid return data."
                )
            })

        physically_out = outstanding_by_product.get(
            product.pk,
            0,
        )

        physically_available = max(
            0,
            product.total_quantity - physically_out,
        )

        if item.quantity > physically_available:
            raise ValidationError({
                "items": (
                    f"Insufficient physical stock for "
                    f"{product.name}. "
                    f"Required: {item.quantity}. "
                    f"Available: {physically_available}."
                )
            })

    rental.status = Rental.Status.ACTIVE

    rental.save(
        update_fields=["status"]
    )

    return load_rental_details(rental)



@transaction.atomic
def return_rental_items(shop, rental_id, items):
    rental = _get_locked_rental(
        shop,
        rental_id,
    )

    if rental.status != Rental.Status.ACTIVE:
        raise ValidationError({
            "detail": (
                "Items can only be returned "
                "for an ACTIVE rental."
            )
        })

    if not items:
        raise ValidationError({
            "items": "At least one item is required."
        })

    item_ids = [
        item["rental_item_id"]
        for item in items
    ]

    if len(item_ids) != len(set(item_ids)):
        raise ValidationError({
            "items": (
                "The same rental item "
                "cannot appear twice."
            )
        })

    rental_items, _ = (
        _get_items_and_lock_products(rental)
    )

    items_by_id = {
        item.pk: item
        for item in rental_items
    }

    changed_items = []

    for data in items:
        item_id = data["rental_item_id"]

        item = items_by_id.get(item_id)

        if item is None:
            raise ValidationError({
                "items": (
                    f"Rental item {item_id} "
                    "does not belong to this rental."
                )
            })

        new_returned = data["returned_quantity"]

        if new_returned < item.returned_quantity:
            raise ValidationError({
                "returned_quantity": (
                    f"Returned quantity cannot decrease. "
                    f"Previously returned: "
                    f"{item.returned_quantity}."
                )
            })

        if new_returned > item.quantity:
            raise ValidationError({
                "returned_quantity": (
                    f"Cannot return more than "
                    f"{item.quantity} dispatched units."
                )
            })

        if new_returned == item.returned_quantity:
            continue

        item.returned_quantity = new_returned

        changed_items.append(item)

    if changed_items:
        RentalItem.objects.bulk_update(
            changed_items,
            ["returned_quantity"],
        )

    return load_rental_details(rental)


def calculate_total_paid(rental):
    return sum(
        (
            payment.amount
            for payment in rental.payments.all()
        ),
        Decimal("0.00"),
    )


def calculate_outstanding_balance(rental):
    if rental.status == Rental.Status.CANCELLED:
        return Decimal("0.00")

    total_charge = calculate_rental_total(rental)
    total_paid = calculate_total_paid(rental)

    return total_charge - total_paid



@transaction.atomic
def cancel_rental(shop, rental_id):
    rental = _get_locked_rental(
        shop,
        rental_id,
    )

    if rental.status != Rental.Status.BOOKED:
        raise ValidationError({
            "detail": (
                "Only a BOOKED rental "
                "can be cancelled."
            )
        })

    if rental.payments.exists():
        raise ValidationError({
            "detail": (
                "A rental with recorded payments "
                "cannot be cancelled."
            )
        })

    _get_items_and_lock_products(rental)

    rental.status = Rental.Status.CANCELLED

    rental.save(
        update_fields=["status"]
    )

    return load_rental_details(rental)




@transaction.atomic
def complete_rental(shop, rental_id):
    rental = _get_locked_rental(
        shop,
        rental_id,
    )

    if rental.status != Rental.Status.ACTIVE:
        raise ValidationError({
            "detail": (
                "Only an ACTIVE rental "
                "can be completed."
            )
        })

    items, _ = (
        _get_items_and_lock_products(rental)
    )

    has_outstanding_items = any(
        item.returned_quantity != item.quantity
        for item in items
    )

    if has_outstanding_items:
        raise ValidationError({
            "detail": (
                "All dispatched items must be "
                "returned before completion."
            )
        })

    outstanding = calculate_outstanding_balance(
        rental
    )

    if outstanding != Decimal("0.00"):
        raise ValidationError({
            "detail": (
                f"Rental balance must be zero. "
                f"Current balance: "
                f"{outstanding:.2f} BDT."
            )
        })

    rental.status = Rental.Status.COMPLETED

    rental.save(
        update_fields=["status"]
    )

    return load_rental_details(rental)
