
from rest_framework import serializers


class DashboardSerializer(serializers.Serializer):

    total_products = serializers.IntegerField(
        read_only=True
    )

    active_rentals = serializers.IntegerField(
        read_only=True
    )

    physically_outstanding_units = (
        serializers.IntegerField(
            read_only=True
        )
    )

    outstanding_receivables = serializers.CharField(
        read_only=True
    )
