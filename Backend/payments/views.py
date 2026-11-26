
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_spectacular.utils import extend_schema

from shops.permissions import IsShopMember
from shops.services import get_user_shop

from rentals.serializers import RentalReadSerializer

from .serializers import PaymentCreateSerializer
from .services import record_payment
from typing import cast
from decimal import Decimal

class RentalPaymentCreateView(APIView):

    permission_classes = [
        IsAuthenticated,
        IsShopMember,
    ]

    @extend_schema(
        request=PaymentCreateSerializer,
        responses={201: RentalReadSerializer},
    )
    def post(self, request, pk):
        serializer = PaymentCreateSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        shop = get_user_shop(request.user)

        data = cast(
            dict[str, Decimal],
            serializer.validated_data,
        )

        rental = record_payment(
            shop=shop,
            rental_id=pk,
            amount=data["amount"],
        )

        return Response(
            RentalReadSerializer(rental).data,
            status=status.HTTP_201_CREATED,
        )
