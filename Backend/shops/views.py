
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from .models import Shop, ShopStaff
from .permissions import IsShopOwner
from .serializers import (
    ShopSerializer,
    AssignStaffSerializer,
    ShopStaffSerializer,
)
from .services import get_user_shop, assign_existing_staff


class ShopCreateView(generics.CreateAPIView):
    serializer_class = ShopSerializer
    permission_classes = [IsAuthenticated]


class CurrentShopView(generics.RetrieveAPIView):
    serializer_class = ShopSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        shop = get_user_shop(self.request.user)

        if shop is None:
            return get_object_or_404(
                Shop,
                pk=None,
            )

        return shop


class ShopStaffListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsShopOwner]

    @extend_schema(
        responses=ShopStaffSerializer(many=True)
    )
    def get(self, request):
        shop = Shop.objects.get(
            owner_id=request.user.pk
        )

        staff = (
            ShopStaff.objects
            .filter(shop=shop)
            .select_related("user")
            .order_by("id")
        )

        serializer = ShopStaffSerializer(
            staff,
            many=True,
        )

        return Response(serializer.data)

    @extend_schema(
        request=AssignStaffSerializer,
        responses={201: ShopStaffSerializer},
    )
    def post(self, request):
        serializer = AssignStaffSerializer(
            data=request.data
        )

        serializer.is_valid(raise_exception=True)

        shop = Shop.objects.get(
            owner_id=request.user.pk
        )

        membership = assign_existing_staff(
            shop=shop,
            email=serializer.validated_data["email"],
        )

        result = ShopStaffSerializer(membership)

        return Response(
            result.data,
            status=status.HTTP_201_CREATED,
        )
