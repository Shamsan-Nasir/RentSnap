
from decimal import Decimal
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from shops.models import Shop
from inventory.models import Product
from .models import Customer, Rental, RentalItem


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
