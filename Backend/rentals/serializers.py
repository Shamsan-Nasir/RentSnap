
from rest_framework import serializers
from .models import Rental, RentalItem
from .services import rental_days, calculate_rental_total

from .models import Customer


class CustomerSerializer(serializers.ModelSerializer):

    class Meta:
        model = Customer

        fields = [
            "id",
            "name",
            "phone",
            "notes",
            "created_at",
        ]

        read_only_fields = [
            "id",
            "created_at",
        ]

    def validate_phone(self, value):
        phone = value.strip()

        if not phone:
            raise serializers.ValidationError(
                "Phone number cannot be empty."
            )

        return phone


class RentalBookingItemSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1)

    quantity = serializers.IntegerField(
        min_value=1,
        max_value=2147483647,
    )


class RentalBookingSerializer(serializers.Serializer):
    customer_id = serializers.IntegerField(min_value=1)

    start_date = serializers.DateField()
    end_date = serializers.DateField()

    items = RentalBookingItemSerializer(
        many=True,
        allow_empty=False,
    )


class RentalItemReadSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = RentalItem

        fields = [
            "id",
            "product_id",
            "quantity",
            "returned_quantity",
            "daily_rate_snapshot",
        ]

        read_only_fields = fields


class RentalReadSerializer(serializers.ModelSerializer):
    customer_id = serializers.IntegerField(read_only=True)

    items = RentalItemReadSerializer(
        many=True,
        read_only=True,
    )

    rental_days = serializers.SerializerMethodField()
    total_charge = serializers.SerializerMethodField()

    class Meta:
        model = Rental

        fields = [
            "id",
            "customer_id",
            "start_date",
            "end_date",
            "status",
            "rental_days",
            "total_charge",
            "items",
            "created_at",
        ]

        read_only_fields = fields

    def get_rental_days(self, obj) -> int:
        return rental_days(
            obj.start_date,
            obj.end_date,
        )

    def get_total_charge(self, obj) -> str:
        total = calculate_rental_total(obj)

        return format(total, ".2f")


class AvailabilityQuerySerializer(serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1)

    start_date = serializers.DateField()
    end_date = serializers.DateField()


class AvailabilityResponseSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()

    total_quantity = serializers.IntegerField()
    available_quantity = serializers.IntegerField()
