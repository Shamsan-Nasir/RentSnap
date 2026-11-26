
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from shops.permissions import IsShopMember
from shops.services import get_user_shop

from .models import Customer
from .serializers import CustomerSerializer


from django.db.models import prefetch_related_objects

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_spectacular.utils import extend_schema

from .serializers import (
    RentalBookingSerializer,
    RentalReadSerializer,
)

from rest_framework.exceptions import NotFound, ValidationError

from inventory.models import Product
from inventory.services import available_quantity

from .serializers import (
    AvailabilityQuerySerializer,
    AvailabilityResponseSerializer,
)

from .services import validate_booking_dates

from .services import create_rental


class CustomerListCreateView(generics.ListCreateAPIView):

    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticated, IsShopMember]

    search_fields = ["name", "phone"]
    ordering_fields = ["name", "created_at"]
    ordering = ["-created_at", "-id"]

    def get_queryset(self):
        shop = get_user_shop(self.request.user)

        return Customer.objects.filter(
            shop=shop
        ).order_by("-created_at", "-id")

    def perform_create(self, serializer):
        shop = get_user_shop(self.request.user)

        serializer.save(shop=shop)


class CustomerDetailView(generics.RetrieveUpdateAPIView):

    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticated, IsShopMember]

    http_method_names = [
        "get",
        "patch",
        "head",
        "options",
    ]

    def get_queryset(self):
        shop = get_user_shop(self.request.user)

        return Customer.objects.filter(
            shop=shop
        )
        

class RentalCreateView(APIView):
    permission_classes = [
        IsAuthenticated,
        IsShopMember,
    ]

    @extend_schema(
        request=RentalBookingSerializer,
        responses={201: RentalReadSerializer},
    )
    def post(self, request):
        serializer = RentalBookingSerializer(
            data=request.data
        )

        serializer.is_valid(raise_exception=True)

        shop = get_user_shop(request.user)

        rental = create_rental(
            shop=shop,
            **serializer.validated_data,
        )

        prefetch_related_objects(
            [rental],
            "items",
        )

        response_serializer = RentalReadSerializer(
            rental
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
        )
        

class ProductAvailabilityView(APIView):
    permission_classes = [
        IsAuthenticated,
        IsShopMember,
    ]

    @extend_schema(
        parameters=[AvailabilityQuerySerializer],
        responses=AvailabilityResponseSerializer,
    )
    def get(self, request):
        serializer = AvailabilityQuerySerializer(
            data=request.query_params
        )

        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        today = validate_booking_dates(
            data["start_date"],
            data["end_date"],
        )

        shop = get_user_shop(request.user)

        product = Product.objects.filter(
            pk=data["product_id"],
            shop=shop,
        ).first()

        if product is None:
            raise NotFound("Product not found.")

        if not product.is_active:
            raise ValidationError({
                "product_id": "This product is inactive."
            })

        available = available_quantity(
            product=product,
            start_date=data["start_date"],
            end_date=data["end_date"],
            today=today,
        )

        result = {
            "product_id": product.pk,
            "start_date": data["start_date"],
            "end_date": data["end_date"],
            "total_quantity": product.total_quantity,
            "available_quantity": available,
        }

        return Response(
            AvailabilityResponseSerializer(result).data
        )
