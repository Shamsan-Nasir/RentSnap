
from django.urls import path
from .views import (health_check, DashboardView)

urlpatterns = [
    path("health/", health_check, name="health-check"),
    path(
    "dashboard/",
    DashboardView.as_view(),
    name="dashboard",
),
]
