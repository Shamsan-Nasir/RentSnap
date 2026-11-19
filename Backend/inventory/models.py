
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models


class Product(models.Model):
    shop = models.ForeignKey(
        "shops.Shop",
        on_delete=models.PROTECT,
        related_name="products",
    )

    name = models.CharField(max_length=150)

    total_quantity = models.PositiveIntegerField(
        default=0
    )

    daily_rate = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["shop", "is_active"],
                name="product_shop_active_idx",
            ),
        ]

        constraints = [
            models.CheckConstraint(
                condition=models.Q(daily_rate__gt=0),
                name="product_rate_positive",
            ),
        ]

    def __str__(self):
        return self.name
