from django.test import TestCase

# Create your tests here.
from django.urls import reverse
from rest_framework import status


class HealthCheckTests(TestCase):

    def test_health_endpoint(self):
        url = reverse("health-check")
        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["status"],
            "ok",
        )
