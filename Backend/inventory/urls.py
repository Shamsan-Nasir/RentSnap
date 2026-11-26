
from django.urls import path

from .views import (
    ProductListCreateView,
    ProductDetailView,
    ProductStatusView
)


urlpatterns = [
    path(
        "",
        ProductListCreateView.as_view(),
        name="product-list-create",
    ),
    path("<int:pk>/",
        ProductDetailView.as_view(),
        name="product-detail",),
    path(
        "<int:pk>/status/",
        ProductStatusView.as_view(),
        name="product-status",
    ),
]
