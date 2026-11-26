
from django.urls import path

from .views import (
    RentalCreateView,
    ProductAvailabilityView,
)


urlpatterns = [
    path(
        "",
        RentalCreateView.as_view(),
        name="rental-create",
    ),

    path(
        "availability/",
        ProductAvailabilityView.as_view(),
        name="rental-availability",
    ),
]
