
from rest_framework import serializers

from .models import Shop, ShopStaff
from .services import create_shop_for_user


class ShopSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()

    class Meta:
        model = Shop
        fields = ["id", "name", "role", "created_at"]
        read_only_fields = ["id", "role", "created_at"]

    def get_role(self, obj):
        request = self.context["request"]

        if obj.owner_id == request.user.pk:
            return "OWNER"

        return "STAFF"

    def create(self, validated_data):
        request = self.context["request"]

        return create_shop_for_user(
            user=request.user,
            name=validated_data["name"],
        )


class AssignStaffSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        return value.strip().lower()


class ShopStaffSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(
        source="user.email",
        read_only=True,
    )

    class Meta:
        model = ShopStaff
        fields = ["id", "email", "added_at"]
        read_only_fields = ["id", "email", "added_at"]
