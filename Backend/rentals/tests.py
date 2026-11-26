
from decimal import Decimal
from datetime import date, timedelta
from django.urls import reverse
from django.utils import timezone

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from shops.models import Shop
from inventory.models import Product
from .models import Customer, Rental, RentalItem
from .services import calculate_rental_total

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from shops.models import ShopStaff


User = get_user_model()


class RentalModelTests(TestCase):

    def setUp(self):
        user = User.objects.create_user(
            email="owner@example.com",
            password="ExampleSecurePassword123!",
        )

        self.shop = Shop.objects.create(
            name="Test Shop",
            owner=user,
        )

        self.product = Product.objects.create(
            shop=self.shop,
            name="Plastic Chair",
            total_quantity=100,
            daily_rate=Decimal("20.00"),
        )

        self.customer = Customer.objects.create(
            shop=self.shop,
            name="Rahim",
            phone="01700000000",
        )

        today = date.today()

        self.rental = Rental.objects.create(
            shop=self.shop,
            customer=self.customer,
            start_date=today,
            end_date=today + timedelta(days=2),
        )

    def test_rental_defaults_to_booked(self):
        self.assertEqual(
            self.rental.status,
            Rental.Status.BOOKED,
        )

    def test_cannot_return_more_than_booked(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                RentalItem.objects.create(
                    rental=self.rental,
                    product=self.product,
                    quantity=30,
                    returned_quantity=31,
                    daily_rate_snapshot=Decimal("20.00"),
                )

    def test_product_price_change_preserves_snapshot(self):
        item = RentalItem.objects.create(
            rental=self.rental,
            product=self.product,
            quantity=30,
            daily_rate_snapshot=Decimal("20.00"),
        )

        self.product.daily_rate = Decimal("25.00")
        self.product.save()

        item.refresh_from_db()

        self.assertEqual(
            item.daily_rate_snapshot,
            Decimal("20.00"),
        )

    def test_duplicate_product_line_is_rejected(self):
        RentalItem.objects.create(
            rental=self.rental,
            product=self.product,
            quantity=10,
            daily_rate_snapshot=Decimal("20.00"),
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                RentalItem.objects.create(
                    rental=self.rental,
                    product=self.product,
                    quantity=20,
                    daily_rate_snapshot=Decimal("20.00"),
                )



class CustomerAPITests(APITestCase):

    def setUp(self):
        self.owner = User.objects.create_user(
            email="customer-owner@example.com",
            password="ExampleSecurePassword123!",
        )

        self.staff = User.objects.create_user(
            email="customer-staff@example.com",
            password="ExampleSecurePassword123!",
        )

        self.other_owner = User.objects.create_user(
            email="other-owner@example.com",
            password="ExampleSecurePassword123!",
        )

        self.shop = Shop.objects.create(
            name="Customer Shop",
            owner=self.owner,
        )

        self.other_shop = Shop.objects.create(
            name="Other Shop",
            owner=self.other_owner,
        )

        ShopStaff.objects.create(
            shop=self.shop,
            user=self.staff,
        )

        self.list_url = reverse("customer-list-create")

    def test_staff_can_create_customer(self):
        self.client.force_authenticate(user=self.staff)

        response = self.client.post(
            self.list_url,
            {
                "name": "Rahim Uddin",
                "phone": "01712345678",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        customer = Customer.objects.get(
            pk=response.data["id"]
        )

        self.assertEqual(customer.shop, self.shop)

    def test_customer_search_by_phone(self):
        Customer.objects.create(
            shop=self.shop,
            name="Rahim",
            phone="01712345678",
        )

        Customer.objects.create(
            shop=self.shop,
            name="Karim",
            phone="01812345678",
        )

        self.client.force_authenticate(user=self.staff)

        response = self.client.get(
            self.list_url,
            {"search": "01712345678"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(response.data["count"], 1)

    def test_staff_can_edit_customer(self):
        customer = Customer.objects.create(
            shop=self.shop,
            name="Rahim",
            phone="01712345678",
        )

        self.client.force_authenticate(user=self.staff)

        response = self.client.patch(
            reverse("customer-detail", args=[customer.pk]),
            {"phone": "01812345678"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        customer.refresh_from_db()

        self.assertEqual(
            customer.phone,
            "01812345678",
        )

    def test_other_shop_cannot_access_customer(self):
        customer = Customer.objects.create(
            shop=self.shop,
            name="Private Customer",
            phone="01712345678",
        )

        self.client.force_authenticate(
            user=self.other_owner
        )

        detail_url = reverse(
            "customer-detail",
            args=[customer.pk],
        )

        response = self.client.get(detail_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

        response = self.client.patch(
            detail_url,
            {"name": "Changed Name"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_empty_phone_is_rejected(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(
            self.list_url,
            {
                "name": "Rahim",
                "phone": "   ",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )


class RentalBookingTests(APITestCase):

    def setUp(self):
        self.owner = User.objects.create_user(
            email="booking-owner@example.com",
            password="ExampleSecurePassword123!",
        )

        self.staff = User.objects.create_user(
            email="booking-staff@example.com",
            password="ExampleSecurePassword123!",
        )

        self.shop = Shop.objects.create(
            name="Booking Test Shop",
            owner=self.owner,
        )

        ShopStaff.objects.create(
            shop=self.shop,
            user=self.staff,
        )

        self.customer = Customer.objects.create(
            shop=self.shop,
            name="Rahim",
            phone="01712345678",
        )

        self.chair = Product.objects.create(
            shop=self.shop,
            name="Plastic Chair",
            total_quantity=100,
            daily_rate=Decimal("20.00"),
        )

        self.table = Product.objects.create(
            shop=self.shop,
            name="Folding Table",
            total_quantity=20,
            daily_rate=Decimal("150.00"),
        )

        self.start = (
            timezone.localdate() + timedelta(days=1)
        )

        self.end = self.start + timedelta(days=2)

        self.url = reverse("rental-create")

        self.client.force_authenticate(
            user=self.staff
        )

    def booking_payload(self, items=None):
        if items is None:
            items = [
                {
                    "product_id": self.chair.pk,
                    "quantity": 30,
                },
                {
                    "product_id": self.table.pk,
                    "quantity": 2,
                },
            ]

        return {
            "customer_id": self.customer.pk,
            "start_date": self.start.isoformat(),
            "end_date": self.end.isoformat(),
            "items": items,
        }

    def book_chairs(self, quantity):
        data = self.booking_payload(
            items=[
                {
                    "product_id": self.chair.pk,
                    "quantity": quantity,
                }
            ]
        )

        return self.client.post(
            self.url,
            data,
            format="json",
        )

    def test_staff_can_create_rental(self):
        response = self.client.post(
            self.url,
            self.booking_payload(),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            response.data["status"],
            "BOOKED",
        )

        self.assertEqual(
            response.data["rental_days"],
            3,
        )

        self.assertEqual(
            response.data["total_charge"],
            "2700.00",
        )

        self.assertEqual(Rental.objects.count(), 1)
        self.assertEqual(RentalItem.objects.count(), 2)

    def test_overbooking_is_rejected(self):
        first = self.book_chairs(80)

        self.assertEqual(
            first.status_code,
            status.HTTP_201_CREATED,
        )

        second = self.book_chairs(30)

        self.assertEqual(
            second.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(Rental.objects.count(), 1)

    def test_non_overlapping_booking_is_allowed(self):
        self.book_chairs(100)

        self.start = self.end + timedelta(days=1)
        self.end = self.start + timedelta(days=2)

        response = self.book_chairs(100)

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

    def test_same_day_rental_cost(self):
        self.end = self.start

        response = self.book_chairs(10)

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            response.data["rental_days"],
            1,
        )

        self.assertEqual(
            response.data["total_charge"],
            "200.00",
        )

    def test_booking_over_30_days_is_rejected(self):
        self.end = self.start + timedelta(days=30)

        response = self.book_chairs(10)

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_past_booking_is_rejected(self):
        self.start = (
            timezone.localdate() - timedelta(days=1)
        )

        response = self.book_chairs(10)

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_archived_product_is_rejected(self):
        self.chair.is_active = False
        self.chair.save()

        response = self.book_chairs(10)

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_duplicate_product_is_rejected(self):
        data = self.booking_payload(
            items=[
                {
                    "product_id": self.chair.pk,
                    "quantity": 10,
                },
                {
                    "product_id": self.chair.pk,
                    "quantity": 20,
                },
            ]
        )

        response = self.client.post(
            self.url,
            data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_failed_booking_creates_no_records(self):
        data = self.booking_payload(
            items=[
                {
                    "product_id": self.chair.pk,
                    "quantity": 10,
                },
                {
                    "product_id": self.table.pk,
                    "quantity": 50,
                },
            ]
        )

        response = self.client.post(
            self.url,
            data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(Rental.objects.count(), 0)
        self.assertEqual(RentalItem.objects.count(), 0)

    def test_price_snapshot_is_preserved(self):
        response = self.book_chairs(10)

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        rental = Rental.objects.get(
            pk=response.data["id"]
        )

        self.chair.daily_rate = Decimal("25.00")
        self.chair.save()

        self.assertEqual(
            calculate_rental_total(rental),
            Decimal("600.00"),
        )

    def test_availability_endpoint(self):
        self.book_chairs(30)

        response = self.client.get(
            reverse("rental-availability"),
            {
                "product_id": self.chair.pk,
                "start_date": self.start.isoformat(),
                "end_date": self.end.isoformat(),
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["available_quantity"],
            70,
        )
    
    def test_other_shop_records_are_rejected(self):
        other_owner = User.objects.create_user(
            email="other-booking@example.com",
            password="ExampleSecurePassword123!",
        )

        other_shop = Shop.objects.create(
            name="Other Shop",
            owner=other_owner,
        )

        other_customer = Customer.objects.create(
            shop=other_shop,
            name="Other Customer",
            phone="01812345678",
        )

        other_product = Product.objects.create(
            shop=other_shop,
            name="Private Product",
            total_quantity=100,
            daily_rate=Decimal("50.00"),
        )

        data = self.booking_payload()
        data["customer_id"] = other_customer.pk

        response = self.client.post(
            self.url,
            data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        data = self.booking_payload(
            items=[
                {
                    "product_id": other_product.pk,
                    "quantity": 10,
                }
            ]
        )

        response = self.client.post(
            self.url,
            data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(Rental.objects.count(), 0)

        response = self.client.get(
            reverse("rental-availability"),
            {
                "product_id": other_product.pk,
                "start_date": self.start.isoformat(),
                "end_date": self.end.isoformat(),
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_overdue_units_block_new_booking(self):
        today = timezone.localdate()

        rental = Rental.objects.create(
            shop=self.shop,
            customer=self.customer,
            start_date=today - timedelta(days=5),
            end_date=today - timedelta(days=1),
            status=Rental.Status.ACTIVE,
        )

        RentalItem.objects.create(
            rental=rental,
            product=self.chair,
            quantity=40,
            returned_quantity=10,
            daily_rate_snapshot=Decimal("20.00"),
        )

        response = self.book_chairs(71)

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        response = self.book_chairs(70)

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

    def test_cancelled_rental_releases_stock(self):
        response = self.book_chairs(100)

        rental = Rental.objects.get(
            pk=response.data["id"]
        )

        rental.status = Rental.Status.CANCELLED
        rental.save()

        response = self.book_chairs(100)

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

    def test_peak_is_not_sum_of_separate_bookings(self):
        original_start = self.start
        original_end = self.end

        self.end = self.start
        self.book_chairs(60)

        self.start = original_end
        self.end = original_end
        self.book_chairs(60)

        self.start = original_start
        self.end = original_end

        response = self.book_chairs(40)

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

    def test_invalid_quantity_and_empty_items(self):
        for items in [
            [],
            [
                {
                    "product_id": self.chair.pk,
                    "quantity": 0,
                }
            ],
            [
                {
                    "product_id": self.chair.pk,
                    "quantity": -10,
                }
            ],
        ]:
            with self.subTest(items=items):
                response = self.client.post(
                    self.url,
                    self.booking_payload(items),
                    format="json",
                )

                self.assertEqual(
                    response.status_code,
                    status.HTTP_400_BAD_REQUEST,
                )

        self.assertEqual(Rental.objects.count(), 0)

    def test_unauthenticated_booking_is_rejected(self):
        self.client.force_authenticate(user=None)

        response = self.client.post(
            self.url,
            self.booking_payload(),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

