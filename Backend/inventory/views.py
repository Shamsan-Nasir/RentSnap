
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from shops.permissions import IsShopOwner, IsShopMember
from shops.services import get_user_shop

from .models import Product
from .serializers import (ProductSerializer,ProductStatusSerializer)


from django.db import transaction
from rest_framework.exceptions import ValidationError

from .services import minimum_required_stock


class ProductListCreateView(generics.ListCreateAPIView):

    serializer_class = ProductSerializer

    search_fields = ["name"]
    filterset_fields = ["is_active"]
    ordering_fields = ["name", "daily_rate", "created_at"]

    ordering = ["-created_at", "-id"]

    def get_permissions(self):
        if self.request.method == "POST":
            permission_classes = [
                IsAuthenticated,
                IsShopOwner,
            ]
        else:
            permission_classes = [
                IsAuthenticated,
                IsShopMember,
            ]

        return [
            permission()
            for permission in permission_classes
        ]

    def get_queryset(self):
        shop = get_user_shop(self.request.user)

        return Product.objects.filter(
            shop=shop
        ).order_by("-created_at", "-id")

    def perform_create(self, serializer):
        shop = get_user_shop(self.request.user)

        serializer.save(shop=shop)
        
        

class ProductDetailView(generics.RetrieveUpdateAPIView):

    serializer_class = ProductSerializer

    http_method_names = [
        "get",
        "patch",
        "head",
        "options",
    ]

    def get_permissions(self):
        if self.request.method == "PATCH":
            classes = [IsAuthenticated, IsShopOwner]
        else:
            classes = [IsAuthenticated, IsShopMember]

        return [permission() for permission in classes]

    def get_queryset(self):
        shop = get_user_shop(self.request.user)

        queryset = Product.objects.filter(shop=shop)

        if self.request.method == "PATCH":
            queryset = queryset.select_for_update()

        return queryset

    @transaction.atomic
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(
            request, *args, **kwargs
        )

    def perform_update(self, serializer):
        product = serializer.instance

        new_quantity = serializer.validated_data.get(
            "total_quantity",
            product.total_quantity,
        )

        if new_quantity < product.total_quantity:
            minimum = minimum_required_stock(product)

            if new_quantity < minimum:
                raise ValidationError({
                    "total_quantity": (
                        f"Cannot reduce stock below {minimum}. "
                        "Existing rentals require these units."
                    )
                })

        serializer.save()
        

class ProductStatusView(generics.UpdateAPIView):

    serializer_class = ProductStatusSerializer
    permission_classes = [IsAuthenticated, IsShopOwner]

    http_method_names = ["patch", "options"]

    def get_queryset(self):
        shop = get_user_shop(self.request.user)

        return (
            Product.objects
            .filter(shop=shop)
            .select_for_update()
        )

    @transaction.atomic
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(
            request, *args, **kwargs
        )


