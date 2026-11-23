
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from shops.permissions import IsShopOwner, IsShopMember
from shops.services import get_user_shop

from .models import Product
from .serializers import ProductSerializer


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
