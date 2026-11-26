
from decimal import Decimal

from rest_framework import serializers

from .models import Payment


class PaymentCreateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )


class PaymentReadSerializer(serializers.ModelSerializer):

    class Meta:
        model = Payment

        fields = [
            "id",
            "amount",
            "created_at",
        ]

        read_only_fields = fields
