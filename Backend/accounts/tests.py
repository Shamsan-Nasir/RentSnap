
from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase


User = get_user_model()


class CustomUserTests(APITestCase):

    def setUp(self):
        self.credentials = {
            "email": "rahim@example.com",
            "password": "ExampleSecurePassword123!",
        }

    def test_email_is_identifier(self):
        self.assertEqual(User.USERNAME_FIELD, "email")
        self.assertNotIn(
            "username",
            [field.name for field in User._meta.fields],
        )

    def test_registration(self):
        response = self.client.post(
            reverse("register"),
            self.credentials,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertNotIn("password", response.data)

        self.assertTrue(
            User.objects.filter(
                email="rahim@example.com"
            ).exists()
        )

    def test_duplicate_email(self):
        self.client.post(
            reverse("register"),
            self.credentials,
            format="json",
        )

        response = self.client.post(
            reverse("register"),
            self.credentials,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_login_with_email(self):
        self.client.post(
            reverse("register"),
            self.credentials,
            format="json",
        )

        response = self.client.post(
            reverse("login"),
            {
                "email": "RAHIM@EXAMPLE.COM",
                "password": self.credentials["password"],
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_profile_requires_authentication(self):
        response = self.client.get(
            reverse("current-user")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_create_superuser(self):
        admin_user = User.objects.create_superuser(
            email="admin@example.com",
            password="ExampleSecurePassword123!",
        )

        self.assertTrue(admin_user.is_staff)
        self.assertTrue(admin_user.is_superuser)
        self.assertEqual(
            admin_user.email,
            "admin@example.com",
        )
