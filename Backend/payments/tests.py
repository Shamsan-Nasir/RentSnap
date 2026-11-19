
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from shops.models import Shop
from rentals.models import Customer, Rental
from .models import Payment


User = get_user_model()


class PaymentModelTests(TestCase):

    def setUp(self):
        user = User.objects.create_user(
            email="payments@example.com",
            password="ExampleSecurePassword123!",
        )

        shop = Shop.objects.create(
            name="Payment Test Shop",
            owner=user,
        )

        customer = Customer.objects.create(
            shop=shop,
            name="Test Customer",
            phone="01700000001",
        )

        self.rental = Rental.objects.create(
            shop=shop,
            customer=customer,
            start_date=date.today(),
            end_date=date.today(),
        )

    def test_positive_payment_is_saved(self):
        payment = Payment.objects.create(
            rental=self.rental,
            amount=Decimal("500.00"),
        )

        self.assertEqual(
            payment.amount,
            Decimal("500.00"),
        )

    def test_zero_payment_is_rejected(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Payment.objects.create(
                    rental=self.rental,
                    amount=Decimal("0.00"),
                )
