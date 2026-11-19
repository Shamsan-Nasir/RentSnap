
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import IntegrityError, transaction
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.core.exceptions import ValidationError as DjangoValidationError

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
    )

    class Meta:
        model = User
        fields = ["id", "email", "password"]
        read_only_fields = ["id"]

    def validate_email(self, value):
        email = value.strip().lower()

        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError(
                "This email is already registered."
            )

        return email

  
    def validate(self, attrs):
        user = User(email=attrs["email"])

        try:
            validate_password(
                attrs["password"],
                user=user,
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError({
                "password": exc.messages
            }) from exc

        return attrs

    def create(self, validated_data):
        try:
            with transaction.atomic():
                return User.objects.create_user(
                    **validated_data
                )
        except IntegrityError:
            raise serializers.ValidationError({
                "email": "This email is already registered."
            })


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email"]
        read_only_fields = ["id", "email"]



class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):

    def validate(self, attrs):
        attrs["email"] = attrs["email"].strip().lower()
        return super().validate(attrs)
