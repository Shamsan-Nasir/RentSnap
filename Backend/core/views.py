from django.shortcuts import render

# Create your views here.

from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_spectacular.utils import extend_schema

from shops.permissions import IsShopMember
from shops.services import get_user_shop

from .serializers import DashboardSerializer
from .services import get_dashboard_summary

@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    return Response({
        "status": "ok",
        "service": "RentSnap API",
    })
    

class DashboardView(APIView):

    permission_classes = [
        IsAuthenticated,
        IsShopMember,
    ]

    @extend_schema(
        responses={200: DashboardSerializer},
    )
    def get(self, request):

        shop = get_user_shop(request.user)

        summary = get_dashboard_summary(shop)

        serializer = DashboardSerializer(summary)

        return Response(serializer.data)
    
