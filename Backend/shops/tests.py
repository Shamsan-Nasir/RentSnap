
from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from .models import Shop, ShopStaff


User = get_user_model()


class ShopTests(APITestCase):

    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@example.com",
            password="ExampleSecurePassword123!",
        )

        self.staff = User.objects.create_user(
            email="staff@example.com",
            password="ExampleSecurePassword123!",
        )

        self.other_owner = User.objects.create_user(
            email="other@example.com",
            password="ExampleSecurePassword123!",
        )

    def login_as(self, user):
        self.client.force_authenticate(user=user)

    def create_shop(self, user, name="Rental Shop"):
        self.login_as(user)

        return self.client.post(
            reverse("shop-create"),
            {"name": name},
            format="json",
        )

    def test_owner_can_create_shop(self):
        response = self.create_shop(self.owner)

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(response.data["role"], "OWNER")
        self.assertEqual(Shop.objects.count(), 1)

    def test_owner_cannot_create_second_shop(self):
        self.create_shop(self.owner)

        response = self.create_shop(
            self.owner,
            "Second Shop",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_owner_can_assign_registered_staff(self):
        self.create_shop(self.owner)

        response = self.client.post(
            reverse("shop-staff"),
            {"email": self.staff.email},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertTrue(
            ShopStaff.objects.filter(
                user=self.staff
            ).exists()
        )

    def test_unregistered_staff_is_rejected(self):
        self.create_shop(self.owner)

        response = self.client.post(
            reverse("shop-staff"),
            {"email": "unknown@example.com"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_staff_cannot_manage_membership(self):
        self.create_shop(self.owner)

        self.client.post(
            reverse("shop-staff"),
            {"email": self.staff.email},
            format="json",
        )

        self.login_as(self.staff)

        response = self.client.get(
            reverse("shop-staff")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_staff_cannot_create_another_shop(self):
        self.create_shop(self.owner)

        self.client.post(
            reverse("shop-staff"),
            {"email": self.staff.email},
            format="json",
        )

        response = self.create_shop(
            self.staff,
            "Another Shop",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_staff_can_view_own_shop(self):
        self.create_shop(self.owner)

        self.client.post(
            reverse("shop-staff"),
            {"email": self.staff.email},
            format="json",
        )

        self.login_as(self.staff)

        response = self.client.get(
            reverse("shop-me")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(response.data["role"], "STAFF")

    def test_owner_cannot_assign_another_owner(self):
        self.create_shop(self.owner)
        self.create_shop(self.other_owner, "Other Shop")

        self.login_as(self.owner)

        response = self.client.post(
            reverse("shop-staff"),
            {"email": self.other_owner.email},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_shops_are_isolated(self):
        first = self.create_shop(
            self.owner,
            "First Shop",
        )

        second = self.create_shop(
            self.other_owner,
            "Second Shop",
        )

        self.login_as(self.owner)

        response = self.client.get(
            reverse("shop-me")
        )

        self.assertEqual(
            response.data["id"],
            first.data["id"],
        )

        self.assertNotEqual(
            response.data["id"],
            second.data["id"],
        )

    def test_user_without_shop_gets_404(self):
        self.login_as(self.staff)

        response = self.client.get(
            reverse("shop-me")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_unauthenticated_user_cannot_create_shop(self):
        response = self.client.post(
            reverse("shop-create"),
            {"name": "Unauthorized Shop"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
