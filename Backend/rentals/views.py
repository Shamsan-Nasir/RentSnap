
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

from .serializers import RentalReturnSerializer

from .services import (
    dispatch_rental,
    return_rental_items,
    cancel_rental,
    complete_rental,
)

from .services import load_rental_details

from .models import Rental
from .serializers import RentalListSerializer

from .services import rental_detail_prefetches

from .filters import RentalFilter

class RentalDetailView(generics.RetrieveAPIView):

    permission_classes = [
        IsAuthenticated,
        IsShopMember,
    ]

    serializer_class = RentalReadSerializer

    filter_backends = []

    def get_queryset(self):
        shop = get_user_shop(self.request.user)

        return (
            Rental.objects
            .filter(shop=shop)
            .select_related("customer")
            .prefetch_related(
                *rental_detail_prefetches()
            )
        )


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
        


class RentalCreateView(generics.ListAPIView):

    permission_classes = [
        IsAuthenticated,
        IsShopMember,
    ]

    serializer_class = RentalListSerializer
    
    filterset_class = RentalFilter

    search_fields = [
        "customer__name",
        "customer__phone",
    ]

    ordering_fields = [
        "id",
        "start_date",
        "end_date",
        "created_at",
    ]

    ordering = [
        "-created_at",
        "-id",
    ]

    def get_queryset(self):
        shop = get_user_shop(self.request.user)

        return (
            Rental.objects
            .filter(shop=shop)
            .select_related("customer")
            .prefetch_related(
                "items",
                "payments",
            )
            .order_by("-created_at", "-pk")
        )

    @extend_schema(
        request=RentalBookingSerializer,
        responses={201: RentalReadSerializer},
    )
    def post(self, request):
        serializer = RentalBookingSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        shop = get_user_shop(request.user)

        rental = create_rental(
            shop=shop,
            **serializer.validated_data,
        )

        load_rental_details(rental)

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


class RentalDispatchView(APIView):

    permission_classes = [
        IsAuthenticated,
        IsShopMember,
    ]

    @extend_schema(
        request=None,
        responses={200: RentalReadSerializer},
    )
    def post(self, request, pk):
        shop = get_user_shop(request.user)

        rental = dispatch_rental(
            shop=shop,
            rental_id=pk,
        )

        return Response(
            RentalReadSerializer(rental).data,
            status=status.HTTP_200_OK,
        )


class RentalReturnView(APIView):

    permission_classes = [
        IsAuthenticated,
        IsShopMember,
    ]

    @extend_schema(
        request=RentalReturnSerializer,
        responses={200: RentalReadSerializer},
    )
    def post(self, request, pk):
        serializer = RentalReturnSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        shop = get_user_shop(request.user)

        rental = return_rental_items(
            shop=shop,
            rental_id=pk,
            items=serializer.validated_data["items"],
        )

        return Response(
            RentalReadSerializer(rental).data,
            status=status.HTTP_200_OK,
        )



class RentalCancelView(APIView):

    permission_classes = [
        IsAuthenticated,
        IsShopMember,
    ]

    @extend_schema(
        request=None,
        responses={200: RentalReadSerializer},
    )
    def post(self, request, pk):
        shop = get_user_shop(request.user)

        rental = cancel_rental(
            shop=shop,
            rental_id=pk,
        )

        return Response(
            RentalReadSerializer(rental).data,
            status=status.HTTP_200_OK,
        )


class RentalCompleteView(APIView):

    permission_classes = [
        IsAuthenticated,
        IsShopMember,
    ]

    @extend_schema(
        request=None,
        responses={200: RentalReadSerializer},
    )
    def post(self, request, pk):
        shop = get_user_shop(request.user)

        rental = complete_rental(
            shop=shop,
            rental_id=pk,
        )

        return Response(
            RentalReadSerializer(rental).data,
            status=status.HTTP_200_OK,
        )
