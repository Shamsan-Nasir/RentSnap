
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connections
from django.test import (
    TransactionTestCase,
    skipUnlessDBFeature,
)
from django.urls import reverse
from django.utils import timezone

from rest_framework.test import APIClient

from shops.models import Shop
from inventory.models import Product

from .models import Customer, Rental


User = get_user_model()


class BookingConcurrencyTests(TransactionTestCase):

    @skipUnlessDBFeature("has_select_for_update")
    def test_concurrent_bookings_do_not_overbook(self):
        owner = User.objects.create_user(
            email="concurrency@example.com",
            password="ExampleSecurePassword123!",
        )

        shop = Shop.objects.create(
            name="Concurrency Test Shop",
            owner=owner,
        )

        customer = Customer.objects.create(
            shop=shop,
            name="Test Customer",
            phone="01712345678",
        )

        product = Product.objects.create(
            shop=shop,
            name="Plastic Chair",
            total_quantity=100,
            daily_rate=Decimal("20.00"),
        )

        start = (
            timezone.localdate() + timedelta(days=1)
        )

        payload = {
            "customer_id": customer.pk,
            "start_date": start.isoformat(),
            "end_date": start.isoformat(),
            "items": [
                {
                    "product_id": product.pk,
                    "quantity": 60,
                }
            ],
        }

        barrier = Barrier(2)

        def book():
            close_old_connections()

            try:
                client = APIClient()

                client.force_authenticate(user=owner)

                barrier.wait(timeout=10)

                response = client.post(
                    reverse("rental-create"),
                    payload,
                    format="json",
                )

                return response.status_code

            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(book)
            second = pool.submit(book)

            results = [
                first.result(timeout=30),
                second.result(timeout=30),
            ]

        self.assertEqual(
            sorted(results),
            [201, 400],
        )

        self.assertEqual(Rental.objects.count(), 1)
