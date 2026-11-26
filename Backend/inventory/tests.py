
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from shops.models import Shop, ShopStaff
from .models import Product


from datetime import timedelta
from django.utils import timezone

from rentals.models import Customer, Rental, RentalItem

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
        

class ProductUpdateTests(APITestCase):

    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner-edit@example.com",
            password="ExampleSecurePassword123!",
        )

        self.staff = User.objects.create_user(
            email="staff-edit@example.com",
            password="ExampleSecurePassword123!",
        )

        self.shop = Shop.objects.create(
            name="Test Rental Shop",
            owner=self.owner,
        )

        ShopStaff.objects.create(
            shop=self.shop,
            user=self.staff,
        )

        self.product = Product.objects.create(
            shop=self.shop,
            name="Plastic Chair",
            total_quantity=100,
            daily_rate=Decimal("20.00"),
        )

        self.customer = Customer.objects.create(
            shop=self.shop,
            name="Test Customer",
            phone="01712345678",
        )

        self.detail_url = reverse(
            "product-detail",
            args=[self.product.pk],
        )

        self.status_url = reverse(
            "product-status",
            args=[self.product.pk],
        )

        self.client.force_authenticate(user=self.owner)

    def add_rental(
        self,
        quantity,
        start,
        end,
        rental_status=Rental.Status.BOOKED,
        returned=0,
    ):
        rental = Rental.objects.create(
            shop=self.shop,
            customer=self.customer,
            start_date=start,
            end_date=end,
            status=rental_status,
        )

        return RentalItem.objects.create(
            rental=rental,
            product=self.product,
            quantity=quantity,
            returned_quantity=returned,
            daily_rate_snapshot=Decimal("20.00"),
        )

    def test_owner_can_edit_product(self):
        response = self.client.patch(
            self.detail_url,
            {"name": "Premium Chair"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.product.refresh_from_db()
        self.assertEqual(
            self.product.name,
            "Premium Chair",
        )

    def test_cannot_reduce_below_overlapping_bookings(self):
        today = timezone.localdate()

        self.add_rental(
            60,
            today + timedelta(days=1),
            today + timedelta(days=3),
        )

        self.add_rental(
            30,
            today + timedelta(days=2),
            today + timedelta(days=4),
        )

        response = self.client.patch(
            self.detail_url,
            {"total_quantity": 89},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.product.refresh_from_db()
        self.assertEqual(self.product.total_quantity, 100)

        response = self.client.patch(
            self.detail_url,
            {"total_quantity": 90},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

    def test_overdue_items_block_stock_reduction(self):
        today = timezone.localdate()

        self.add_rental(
            20,
            today - timedelta(days=3),
            today - timedelta(days=1),
            rental_status=Rental.Status.ACTIVE,
            returned=5,
        )

        response = self.client.patch(
            self.detail_url,
            {"total_quantity": 14},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        response = self.client.patch(
            self.detail_url,
            {"total_quantity": 15},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

    def test_price_change_does_not_change_old_rental(self):
        today = timezone.localdate()

        item = self.add_rental(10, today, today)

        response = self.client.patch(
            self.detail_url,
            {"daily_rate": "25.00"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        item.refresh_from_db()

        self.assertEqual(
            item.daily_rate_snapshot,
            Decimal("20.00"),
        )

    def test_owner_can_archive_and_reactivate(self):
        response = self.client.patch(
            self.status_url,
            {"is_active": False},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.product.refresh_from_db()
        self.assertFalse(self.product.is_active)

        response = self.client.patch(
            self.status_url,
            {"is_active": True},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.product.refresh_from_db()
        self.assertTrue(self.product.is_active)

    def test_staff_cannot_modify_product(self):
        self.client.force_authenticate(user=self.staff)

        response = self.client.patch(
            self.detail_url,
            {"daily_rate": "40.00"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

        response = self.client.patch(
            self.status_url,
            {"is_active": False},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )
        
