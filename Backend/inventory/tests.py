
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from shops.models import Shop, ShopStaff
from .models import Product


User = get_user_model()


class ProductAPITests(APITestCase):

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

        self.shop = Shop.objects.create(
            name="Shop A",
            owner=self.owner,
        )

        self.other_shop = Shop.objects.create(
            name="Shop B",
            owner=self.other_owner,
        )

        ShopStaff.objects.create(
            shop=self.shop,
            user=self.staff,
        )

        self.url = reverse("product-list-create")

        self.product_data = {
            "name": "Plastic Chair",
            "total_quantity": 100,
            "daily_rate": "20.00",
        }

    def test_owner_can_create_product(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(
            self.url,
            self.product_data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        product = Product.objects.get(
            name="Plastic Chair"
        )

        self.assertEqual(product.shop, self.shop)
        self.assertEqual(
            product.daily_rate,
            Decimal("20.00"),
        )

    def test_staff_cannot_create_product(self):
        self.client.force_authenticate(user=self.staff)

        response = self.client.post(
            self.url,
            self.product_data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_staff_can_list_products(self):
        Product.objects.create(
            shop=self.shop,
            name="Plastic Chair",
            total_quantity=100,
            daily_rate=Decimal("20.00"),
        )

        self.client.force_authenticate(user=self.staff)

        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(response.data["count"], 1)

    def test_shop_data_is_isolated(self):
        Product.objects.create(
            shop=self.shop,
            name="Shop A Chair",
            total_quantity=100,
            daily_rate=Decimal("20.00"),
        )

        Product.objects.create(
            shop=self.other_shop,
            name="Shop B Chair",
            total_quantity=50,
            daily_rate=Decimal("25.00"),
        )

        self.client.force_authenticate(user=self.owner)

        response = self.client.get(self.url)

        self.assertEqual(response.data["count"], 1)

        self.assertEqual(
            response.data["results"][0]["name"],
            "Shop A Chair",
        )

    def test_owner_cannot_submit_another_shop_id(self):
        self.client.force_authenticate(user=self.owner)

        data = {
            **self.product_data,
            "shop": self.other_shop.pk,
        }

        response = self.client.post(
            self.url,
            data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        product = Product.objects.get(
            pk=response.data["id"]
        )

        self.assertEqual(product.shop, self.shop)

    def test_zero_rate_is_rejected(self):
        self.client.force_authenticate(user=self.owner)

        data = {
            **self.product_data,
            "daily_rate": "0.00",
        }

        response = self.client.post(
            self.url,
            data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_search_by_product_name(self):
        Product.objects.create(
            shop=self.shop,
            name="Plastic Chair",
            total_quantity=100,
            daily_rate=Decimal("20.00"),
        )

        Product.objects.create(
            shop=self.shop,
            name="Folding Table",
            total_quantity=20,
            daily_rate=Decimal("100.00"),
        )

        self.client.force_authenticate(user=self.owner)

        response = self.client.get(
            self.url,
            {"search": "Chair"},
        )

        self.assertEqual(response.data["count"], 1)

    def test_unauthenticated_request_is_rejected(self):
        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
