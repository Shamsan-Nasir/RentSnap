
from django.urls import path

from payments.views import RentalPaymentCreateView

from .views import (
    RentalCreateView,
    ProductAvailabilityView,
    RentalDispatchView,
    RentalReturnView,
    RentalCancelView,
    RentalCompleteView,
    RentalDetailView,
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

    path(
        "<int:pk>/dispatch/",
        RentalDispatchView.as_view(),
        name="rental-dispatch",
    ),

    path(
        "<int:pk>/return/",
        RentalReturnView.as_view(),
        name="rental-return",
    ),

    path(
        "<int:pk>/payments/",
        RentalPaymentCreateView.as_view(),
        name="rental-payment-create",
    ),

    path(
        "<int:pk>/cancel/",
        RentalCancelView.as_view(),
        name="rental-cancel",
    ),

    path(
        "<int:pk>/complete/",
        RentalCompleteView.as_view(),
        name="rental-complete",
    ),
    path(
    "<int:pk>/",
    RentalDetailView.as_view(),
    name="rental-detail",
),
]
