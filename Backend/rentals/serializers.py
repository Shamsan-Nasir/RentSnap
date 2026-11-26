
from rest_framework import serializers
from .models import Rental, RentalItem
from .services import rental_days, calculate_rental_total

from .models import Customer
from payments.serializers import PaymentReadSerializer

from .services import (
    calculate_total_paid,
    calculate_outstanding_balance,
)

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

    product_id = serializers.IntegerField(
        read_only=True
    )
    product_name = serializers.CharField(
    source="product.name",
    read_only=True,
)
    dispatched_quantity = serializers.SerializerMethodField()

    outstanding_quantity = serializers.SerializerMethodField()

    class Meta:
        model = RentalItem

        fields = [
            "id",
            "product_id",
            "product_name",
            "quantity",
            "dispatched_quantity",
            "returned_quantity",
            "outstanding_quantity",
            "daily_rate_snapshot",
        ]

        read_only_fields = fields


    
    def get_dispatched_quantity(self, obj) -> int:
        if obj.rental.status in [
            Rental.Status.ACTIVE,
            Rental.Status.COMPLETED,
        ]:
            return obj.quantity

        return 0

    def get_outstanding_quantity(self, obj) -> int:
        if obj.rental.status != Rental.Status.ACTIVE:
            return 0

        return obj.quantity - obj.returned_quantity



class RentalReadSerializer(serializers.ModelSerializer):
    customer_id = serializers.IntegerField(
        read_only=True
    )

    items = RentalItemReadSerializer(
        many=True,
        read_only=True,
    )

    payments = PaymentReadSerializer(
        many=True,
        read_only=True,
    )

    rental_days = serializers.SerializerMethodField()

    total_charge = serializers.SerializerMethodField()

    total_paid = serializers.SerializerMethodField()

    outstanding_balance = serializers.SerializerMethodField()

    outstanding_quantity = serializers.SerializerMethodField()

    can_complete = serializers.SerializerMethodField()

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
            "total_paid",
            "outstanding_balance",
            "outstanding_quantity",
            'customer_name',
            "customer_phone",
            "can_complete",
            "items",
            "payments",
            "created_at",
        ]

        read_only_fields = fields

    customer_name = serializers.CharField(
    source="customer.name",
    read_only=True,
    )

    customer_phone = serializers.CharField(
        source="customer.phone",
        read_only=True,
    )
    
    def get_rental_days(self, obj) -> int:
        return rental_days(
            obj.start_date,
            obj.end_date,
        )

    def get_total_charge(self, obj) -> str:
        return format(
            calculate_rental_total(obj),
            ".2f",
        )

    def get_total_paid(self, obj) -> str:
        return format(
            calculate_total_paid(obj),
            ".2f",
        )

    def get_outstanding_balance(self, obj) -> str:
        return format(
            calculate_outstanding_balance(obj),
            ".2f",
        )

    def get_outstanding_quantity(self, obj) -> int:
        if obj.status != Rental.Status.ACTIVE:
            return 0

        return sum(
            item.quantity - item.returned_quantity
            for item in obj.items.all()
        )

    def get_can_complete(self, obj) -> bool:
        if obj.status != Rental.Status.ACTIVE:
            return False

        items = list(obj.items.all())

        return (
            bool(items)
            and all(
                item.returned_quantity == item.quantity
                for item in items
            )
            and calculate_outstanding_balance(obj) == 0
        )


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
    


class RentalReturnItemSerializer(serializers.Serializer):

    rental_item_id = serializers.IntegerField(
        min_value=1
    )

    returned_quantity = serializers.IntegerField(
        min_value=0,
        max_value=2147483647,
    )


class RentalReturnSerializer(serializers.Serializer):

    items = RentalReturnItemSerializer(
        many=True,
        allow_empty=False,
    )


class RentalListSerializer(RentalReadSerializer):

    class Meta(RentalReadSerializer.Meta):

        fields = [
            "id",
            "customer_id",
            "customer_name",
            "customer_phone",
            "start_date",
            "end_date",
            "status",
            "rental_days",
            "total_charge",
            "total_paid",
            "outstanding_balance",
            "outstanding_quantity",
            "created_at",
        ]

        read_only_fields = fields
