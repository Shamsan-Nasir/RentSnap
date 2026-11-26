
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
from django.utils import timezone

from rest_framework.exceptions import ValidationError

from shops.models import Shop
from inventory.models import Product
from rentals.models import Customer, Rental
from rentals.services import (
    create_rental,
    cancel_rental,
)

from .models import Payment
from .services import record_payment


User = get_user_model()


class PaymentConcurrencyTests(TransactionTestCase):

    def setUp(self):
        owner = User.objects.create_user(
            email="payment-race@example.com",
            password="ExampleSecurePassword123!",
        )

        self.shop = Shop.objects.create(
            name="Concurrency Shop",
            owner=owner,
        )

        customer = Customer.objects.create(
            shop=self.shop,
            name="Test Customer",
            phone="01712345678",
        )

        product = Product.objects.create(
            shop=self.shop,
            name="Chair",
            total_quantity=100,
            daily_rate=Decimal("20.00"),
        )

        today = timezone.localdate()

        self.rental = create_rental(
            shop=self.shop,
            customer_id=customer.pk,
            start_date=today,
            end_date=today + timedelta(days=2),
            items=[
                {
                    "product_id": product.pk,
                    "quantity": 30,
                }
            ],
        )

    def run_concurrently(self, actions):
        barrier = Barrier(len(actions))

        def run_action(action):
            close_old_connections()

            try:
                barrier.wait(timeout=10)

                action()

                return True

            except ValidationError:
                return False

            finally:
                connections.close_all()

        with ThreadPoolExecutor(
            max_workers=len(actions)
        ) as pool:
            futures = [
                pool.submit(run_action, action)
                for action in actions
            ]

            return [
                future.result(timeout=30)
                for future in futures
            ]

    def pay(self, amount):
        return record_payment(
            shop=self.shop,
            rental_id=self.rental.pk,
            amount=Decimal(amount),
        )

    @skipUnlessDBFeature("has_select_for_update")
    def test_simultaneous_payments_cannot_overpay(self):
        results = self.run_concurrently([
            lambda: self.pay("1000.00"),
            lambda: self.pay("1000.00"),
        ])

        self.assertEqual(
            sorted(results),
            [False, True],
        )

        self.assertEqual(
            Payment.objects.count(),
            1,
        )

        self.assertEqual(
            Payment.objects.get().amount,
            Decimal("1000.00"),
        )

    @skipUnlessDBFeature("has_select_for_update")
    def test_payment_and_cancellation_are_serialized(self):
        results = self.run_concurrently([
            lambda: self.pay("500.00"),

            lambda: cancel_rental(
                shop=self.shop,
                rental_id=self.rental.pk,
            ),
        ])

        self.assertEqual(
            sorted(results),
            [False, True],
        )

        self.rental.refresh_from_db()

        if self.rental.status == Rental.Status.CANCELLED:
            self.assertEqual(
                Payment.objects.count(),
                0,
            )

        else:
            self.assertEqual(
                self.rental.status,
                Rental.Status.BOOKED,
            )

            self.assertEqual(
                Payment.objects.count(),
                1,
            )
