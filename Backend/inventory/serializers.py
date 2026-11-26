
from rest_framework import serializers

from .models import Product


class ProductSerializer(serializers.ModelSerializer):

    class Meta:
        model = Product

        fields = [
            "id",
            "name",
            "total_quantity",
            "daily_rate",
            "is_active",
            "created_at",
        ]

        read_only_fields = [
            "id",
            "is_active",
            "created_at",
        ]




class ProductStatusSerializer(serializers.ModelSerializer):

    class Meta:
        model = Product
        fields = ["is_active"]

    def validate(self, attrs):
        if "is_active" not in attrs:
            raise serializers.ValidationError({
                "is_active": "This field is required."
            })

        return attrs
