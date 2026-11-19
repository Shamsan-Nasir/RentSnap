
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models


class Customer(models.Model):
    shop = models.ForeignKey(
        "shops.Shop",
        on_delete=models.PROTECT,
        related_name="customers",
    )

    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=30)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["shop", "phone"],
                name="customer_shop_phone_idx",
            ),
        ]

    def __str__(self):
        return self.name


class Rental(models.Model):

    class Status(models.TextChoices):
        BOOKED = "BOOKED", "Booked"
        ACTIVE = "ACTIVE", "Active"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    shop = models.ForeignKey(
        "shops.Shop",
        on_delete=models.PROTECT,
        related_name="rentals",
    )

    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="rentals",
    )

    start_date = models.DateField()
    end_date = models.DateField()

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.BOOKED,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["shop", "status", "end_date"],
                name="rental_shop_status_idx",
            ),
        ]

        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    end_date__gte=models.F("start_date")
                ),
                name="rental_end_after_start",
            ),
        ]

    def __str__(self):
        return f"Rental #{self.pk} - {self.status}"


class RentalItem(models.Model):
    rental = models.ForeignKey(
        Rental,
        on_delete=models.PROTECT,
        related_name="items",
    )

    product = models.ForeignKey(
        "inventory.Product",
        on_delete=models.PROTECT,
        related_name="rental_items",
    )

    quantity = models.PositiveIntegerField()

    returned_quantity = models.PositiveIntegerField(
        default=0
    )

    daily_rate_snapshot = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["rental", "product"],
                name="unique_product_per_rental",
            ),

            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="rental_item_qty_positive",
            ),

            models.CheckConstraint(
                condition=models.Q(
                    returned_quantity__lte=models.F("quantity")
                ),
                name="returned_not_over_booked",
            ),

            models.CheckConstraint(
                condition=models.Q(
                    daily_rate_snapshot__gt=0
                ),
                name="rental_item_rate_positive",
            ),
        ]

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"
