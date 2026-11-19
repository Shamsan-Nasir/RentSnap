
from django.urls import path

from .views import (
    ShopCreateView,
    CurrentShopView,
    ShopStaffListCreateView,
)


urlpatterns = [
    path(
        "",
        ShopCreateView.as_view(),
        name="shop-create",
    ),

    path(
        "me/",
        CurrentShopView.as_view(),
        name="shop-me",
    ),

    path(
        "staff/",
        ShopStaffListCreateView.as_view(),
        name="shop-staff",
    ),
]
