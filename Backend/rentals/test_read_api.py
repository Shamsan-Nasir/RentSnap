
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from rest_framework import status
from rest_framework.test import APITestCase

from shops.models import Shop, ShopStaff
from inventory.models import Product
from payments.models import Payment

from core.services import get_dashboard_summary

from .models import Customer, Rental, RentalItem


User = get_user_model()


class RentalReadAPITests(APITestCase):

    def setUp(self):
        self.owner = User.objects.create_user(
            email="read-owner@example.com",
            password="ExampleSecurePassword123!",
        )

        self.staff = User.objects.create_user(
            email="read-staff@example.com",
            password="ExampleSecurePassword123!",
        )

        self.shop = Shop.objects.create(
            name="Read API Test Shop",
            owner=self.owner,
        )

        ShopStaff.objects.create(
            shop=self.shop,
            user=self.staff,
        )

        self.customer = Customer.objects.create(
            shop=self.shop,
            name="Rahim Uddin",
            phone="01712345678",
        )

        self.other_customer = Customer.objects.create(
            shop=self.shop,
            name="Karim Ahmed",
            phone="01812345678",
        )

        self.product = Product.objects.create(
            shop=self.shop,
            name="Plastic Chair",
            total_quantity=100,
            daily_rate=Decimal("20.00"),
        )

        Product.objects.create(
            shop=self.shop,
            name="Archived Table",
            total_quantity=20,
            daily_rate=Decimal("150.00"),
            is_active=False,
        )

        self.today = timezone.localdate()

        self.booked = self.make_rental(
            rental_status=Rental.Status.BOOKED,
            quantity=10,
            start=self.today + timedelta(days=3),
            paid="100.00",
        )

        self.active = self.make_rental(
            rental_status=Rental.Status.ACTIVE,
            quantity=30,
            returned=20,
            start=self.today,
            paid="500.00",
        )

        self.completed = self.make_rental(
            rental_status=Rental.Status.COMPLETED,
            quantity=5,
            returned=5,
            start=self.today - timedelta(days=4),
            paid="300.00",
            customer=self.other_customer,
        )

        self.cancelled = self.make_rental(
            rental_status=Rental.Status.CANCELLED,
            quantity=10,
            start=self.today + timedelta(days=6),
            customer=self.other_customer,
        )

        self.list_url = reverse("rental-create")
        self.dashboard_url = reverse("dashboard")

        self.client.force_authenticate(
            user=self.staff
        )

    def make_rental(
        self,
        rental_status,
        quantity,
        start,
        returned=0,
        paid="0.00",
        customer=None,
    ):
        rental = Rental.objects.create(
            shop=self.shop,
            customer=customer or self.customer,
            start_date=start,
            end_date=start + timedelta(days=2),
            status=rental_status,
        )

        RentalItem.objects.create(
            rental=rental,
            product=self.product,
            quantity=quantity,
            returned_quantity=returned,
            daily_rate_snapshot=Decimal("20.00"),
        )

        if Decimal(paid) > 0:
            Payment.objects.create(
                rental=rental,
                amount=Decimal(paid),
            )

        return rental
    
    
    def test_staff_can_list_rentals(self):
        response = self.client.get(self.list_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            response.data,
        )

        self.assertEqual(response.data["count"], 4)

        result = response.data["results"][0]

        self.assertIn("customer_name", result)
        self.assertIn("total_paid", result)
        self.assertIn("outstanding_balance", result)

        self.assertNotIn("items", result)
        self.assertNotIn("payments", result)

    def test_rental_detail(self):
        url = reverse(
            "rental-detail",
            args=[self.active.pk],
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            response.data,
        )

        self.assertEqual(
            response.data["customer_name"],
            "Rahim Uddin",
        )

        self.assertEqual(
            response.data["total_charge"],
            "1800.00",
        )

        self.assertEqual(
            response.data["outstanding_balance"],
            "1300.00",
        )

        self.assertEqual(
            response.data["outstanding_quantity"],
            10,
        )

        self.assertEqual(
            response.data["items"][0]["product_name"],
            "Plastic Chair",
        )

        self.assertEqual(
            len(response.data["payments"]),
            1,
        )

    def test_filter_by_status(self):
        response = self.client.get(
            self.list_url,
            {"status": "ACTIVE"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            response.data,
        )

        self.assertEqual(response.data["count"], 1)

        self.assertEqual(
            response.data["results"][0]["id"],
            self.active.pk,
        )

    def test_filter_by_due_dates(self):
        response = self.client.get(
            self.list_url,
            {
                "due_from": self.today.isoformat(),
                "due_to": (
                    self.today + timedelta(days=2)
                ).isoformat(),
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            response.data,
        )

        self.assertEqual(response.data["count"], 1)

        self.assertEqual(
            response.data["results"][0]["id"],
            self.active.pk,
        )

    def test_invalid_filters_are_rejected(self):
        invalid_filters = [
            {"status": "FINISHED"},
            {"due_from": "invalid-date"},
            {
                "due_from": self.today.isoformat(),
                "due_to": (
                    self.today - timedelta(days=1)
                ).isoformat(),
            },
        ]

        for params in invalid_filters:
            with self.subTest(params=params):
                response = self.client.get(
                    self.list_url,
                    params,
                )

                self.assertEqual(
                    response.status_code,
                    status.HTTP_400_BAD_REQUEST,
                    response.data,
                )

    def test_search_by_customer_name_and_phone(self):
        for search in [
            "Rahim",
            "01712345678",
        ]:
            with self.subTest(search=search):
                response = self.client.get(
                    self.list_url,
                    {"search": search},
                )

                self.assertEqual(
                    response.status_code,
                    status.HTTP_200_OK,
                    response.data,
                )

                self.assertEqual(
                    response.data["count"],
                    2,
                )

    def test_filter_by_customer(self):
        response = self.client.get(
            self.list_url,
            {"customer_id": self.customer.pk},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            response.data,
        )

        self.assertEqual(response.data["count"], 2)

    def test_ordering_by_due_date(self):
        response = self.client.get(
            self.list_url,
            {"ordering": "end_date,id"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            response.data,
        )

        returned_dates = [
            rental["end_date"]
            for rental in response.data["results"]
        ]

        self.assertEqual(
            returned_dates,
            sorted(returned_dates),
        )

    
    def test_dashboard_calculations(self):
        response = self.client.get(
            self.dashboard_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            response.data,
        )

        self.assertEqual(
            response.data["total_products"],
            2,
        )

        self.assertEqual(
            response.data["active_rentals"],
            1,
        )

        self.assertEqual(
            response.data["physically_outstanding_units"],
            10,
        )

        self.assertEqual(
            response.data["outstanding_receivables"],
            "1800.00",
        )

    def test_owner_can_view_dashboard(self):
        self.client.force_authenticate(
            user=self.owner
        )

        response = self.client.get(
            self.dashboard_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            response.data,
        )

    def test_dashboard_updates_after_operations(self):
        payment_response = self.client.post(
            reverse(
                "rental-payment-create",
                args=[self.active.pk],
            ),
            {"amount": "300.00"},
            format="json",
        )

        self.assertEqual(
            payment_response.status_code,
            status.HTTP_201_CREATED,
            payment_response.data,
        )

        item = self.active.items.get()

        return_response = self.client.post(
            reverse(
                "rental-return",
                args=[self.active.pk],
            ),
            {
                "items": [
                    {
                        "rental_item_id": item.pk,
                        "returned_quantity": 30,
                    }
                ]
            },
            format="json",
        )

        self.assertEqual(
            return_response.status_code,
            status.HTTP_200_OK,
            return_response.data,
        )

        response = self.client.get(
            self.dashboard_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            response.data,
        )

        self.assertEqual(
            response.data["outstanding_receivables"],
            "1500.00",
        )

        self.assertEqual(
            response.data["physically_outstanding_units"],
            0,
        )

        self.assertEqual(
            response.data["active_rentals"],
            1,
        )

    
    def test_other_shop_data_is_not_visible(self):
        outside_owner = User.objects.create_user(
            email="outside-read@example.com",
            password="ExampleSecurePassword123!",
        )

        outside_shop = Shop.objects.create(
            name="Outside Shop",
            owner=outside_owner,
        )

        outside_customer = Customer.objects.create(
            shop=outside_shop,
            name="Private Customer",
            phone="01912345678",
        )

        outside_product = Product.objects.create(
            shop=outside_shop,
            name="Private Product",
            total_quantity=50,
            daily_rate=Decimal("100.00"),
        )

        outside_rental = Rental.objects.create(
            shop=outside_shop,
            customer=outside_customer,
            start_date=self.today,
            end_date=self.today,
            status=Rental.Status.ACTIVE,
        )

        RentalItem.objects.create(
            rental=outside_rental,
            product=outside_product,
            quantity=10,
            daily_rate_snapshot=Decimal("100.00"),
        )

        response = self.client.get(self.list_url)

        self.assertEqual(response.data["count"], 4)

        response = self.client.get(
            reverse(
                "rental-detail",
                args=[outside_rental.pk],
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

        response = self.client.get(
            self.dashboard_url
        )

        self.assertEqual(
            response.data["total_products"],
            2,
        )

        self.assertEqual(
            response.data["active_rentals"],
            1,
        )

        self.assertEqual(
            response.data["physically_outstanding_units"],
            10,
        )

        self.assertEqual(
            response.data["outstanding_receivables"],
            "1800.00",
        )

    def test_empty_shop_dashboard(self):
        empty_owner = User.objects.create_user(
            email="empty-shop@example.com",
            password="ExampleSecurePassword123!",
        )

        Shop.objects.create(
            name="Empty Shop",
            owner=empty_owner,
        )

        self.client.force_authenticate(
            user=empty_owner
        )

        response = self.client.get(
            self.dashboard_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            response.data,
        )

        self.assertEqual(
            response.data,
            {
                "total_products": 0,
                "active_rentals": 0,
                "physically_outstanding_units": 0,
                "outstanding_receivables": "0.00",
            },
        )

    def test_user_without_shop_is_rejected(self):
        user = User.objects.create_user(
            email="no-shop-read@example.com",
            password="ExampleSecurePassword123!",
        )

        self.client.force_authenticate(user=user)

        for url in [
            self.list_url,
            self.dashboard_url,
        ]:
            response = self.client.get(url)

            self.assertEqual(
                response.status_code,
                status.HTTP_403_FORBIDDEN,
                response.data,
            )

    def test_unauthenticated_requests_are_rejected(self):
        self.client.force_authenticate(user=None)

        for url in [
            self.list_url,
            self.dashboard_url,
        ]:
            response = self.client.get(url)

            self.assertEqual(
                response.status_code,
                status.HTTP_401_UNAUTHORIZED,
                response.data,
            )

    
    def test_rental_pagination(self):
        for i in range(17):
            self.make_rental(
                rental_status=Rental.Status.BOOKED,
                quantity=1,
                start=(
                    self.today + timedelta(days=10)
                ),
            )

        response = self.client.get(self.list_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            response.data,
        )

        self.assertEqual(response.data["count"], 21)

        self.assertEqual(
            len(response.data["results"]),
            20,
        )

        self.assertIsNotNone(
            response.data["next"]
        )

        second_page = self.client.get(
            self.list_url,
            {"page": 2},
        )

        self.assertEqual(
            second_page.status_code,
            status.HTTP_200_OK,
            second_page.data,
        )

        self.assertEqual(
            len(second_page.data["results"]),
            1,
        )

    def test_list_queries_do_not_grow_per_rental(self):
        with CaptureQueriesContext(connection) as first:
            response = self.client.get(self.list_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            response.data,
        )

        for i in range(5):
            self.make_rental(
                rental_status=Rental.Status.BOOKED,
                quantity=1,
                start=(
                    self.today + timedelta(days=10)
                ),
            )

        with CaptureQueriesContext(connection) as second:
            response = self.client.get(self.list_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            response.data,
        )

        self.assertEqual(
            len(first.captured_queries),
            len(second.captured_queries),
        )

    def test_dashboard_query_count(self):
        with self.assertNumQueries(5):
            summary = get_dashboard_summary(
                self.shop
            )

        self.assertEqual(
            summary["outstanding_receivables"],
            "1800.00",
        )

