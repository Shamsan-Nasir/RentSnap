
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from rest_framework import status
from rest_framework.test import APITestCase

from shops.models import Shop, ShopStaff
from inventory.models import Product
from inventory.services import available_quantity
from payments.models import Payment

from .models import Customer, Rental
from .services import create_rental


User = get_user_model()


class RentalSettlementTests(APITestCase):

    def setUp(self):
        self.owner = User.objects.create_user(
            email="settlement-owner@example.com",
            password="ExampleSecurePassword123!",
        )

        self.staff = User.objects.create_user(
            email="settlement-staff@example.com",
            password="ExampleSecurePassword123!",
        )

        self.shop = Shop.objects.create(
            name="Settlement Test Shop",
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

        self.product = Product.objects.create(
            shop=self.shop,
            name="Plastic Chair",
            total_quantity=100,
            daily_rate=Decimal("20.00"),
        )

        self.today = timezone.localdate()

        self.rental = create_rental(
            shop=self.shop,
            customer_id=self.customer.pk,
            start_date=self.today,
            end_date=self.today + timedelta(days=2),
            items=[
                {
                    "product_id": self.product.pk,
                    "quantity": 30,
                }
            ],
        )

        self.item = self.rental.items.get()

        self.client.force_authenticate(
            user=self.staff
        )

    def action_url(self, name):
        return reverse(
            name,
            args=[self.rental.pk],
        )

    def pay(self, amount):
        return self.client.post(
            self.action_url("rental-payment-create"),
            {"amount": amount},
            format="json",
        )

    def dispatch(self):
        return self.client.post(
            self.action_url("rental-dispatch"),
            format="json",
        )

    def return_all(self):
        return self.client.post(
            self.action_url("rental-return"),
            {
                "items": [
                    {
                        "rental_item_id": self.item.pk,
                        "returned_quantity": 30,
                    }
                ]
            },
            format="json",
        )

    def cancel(self):
        return self.client.post(
            self.action_url("rental-cancel"),
            format="json",
        )

    def complete(self):
        return self.client.post(
            self.action_url("rental-complete"),
            format="json",
        )
        
    
    def test_advance_payment_on_booked_rental(self):
        response = self.pay("500.00")

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            response.data["total_charge"],
            "1800.00",
        )

        self.assertEqual(
            response.data["total_paid"],
            "500.00",
        )

        self.assertEqual(
            response.data["outstanding_balance"],
            "1300.00",
        )

        self.assertEqual(
            response.data["status"],
            Rental.Status.BOOKED,
        )

        self.assertEqual(Payment.objects.count(), 1)

    def test_multiple_payments(self):
        first = self.pay("500.00")

        self.assertEqual(
            first.status_code,
            status.HTTP_201_CREATED,
        )

        self.dispatch()

        response = self.pay("1300.00")

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            response.data["total_paid"],
            "1800.00",
        )

        self.assertEqual(
            response.data["outstanding_balance"],
            "0.00",
        )

        self.assertEqual(Payment.objects.count(), 2)

        self.assertEqual(
            [
                payment["amount"]
                for payment in response.data["payments"]
            ],
            ["500.00", "1300.00"],
        )

    def test_overpayment_is_rejected(self):
        self.pay("500.00")

        response = self.pay("1300.01")

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(Payment.objects.count(), 1)

    def test_invalid_payment_amounts(self):
        for amount in [
            "0.00",
            "-100.00",
            "50.123",
            "invalid",
        ]:
            with self.subTest(amount=amount):
                response = self.pay(amount)

                self.assertEqual(
                    response.status_code,
                    status.HTTP_400_BAD_REQUEST,
                )

        self.assertEqual(Payment.objects.count(), 0)

    def test_decimal_precision(self):
        self.pay("0.01")

        response = self.pay("1799.99")

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            response.data["outstanding_balance"],
            "0.00",
        )

    def test_payment_after_full_payment_is_rejected(self):
        self.pay("1800.00")

        response = self.pay("0.01")

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(Payment.objects.count(), 1)

    def test_owner_can_record_payment(self):
        self.client.force_authenticate(
            user=self.owner
        )

        response = self.pay("500.00")

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

    def test_payment_methods_are_restricted(self):
        self.pay("500.00")

        url = self.action_url(
            "rental-payment-create"
        )

        patch_response = self.client.patch(
            url,
            {"amount": "200.00"},
            format="json",
        )

        delete_response = self.client.delete(url)

        self.assertEqual(
            patch_response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )

        self.assertEqual(
            delete_response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )

        self.assertEqual(
            Payment.objects.get().amount,
            Decimal("500.00"),
        )
    
    
    def test_unpaid_booked_rental_can_be_cancelled(self):
        response = self.cancel()

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.rental.refresh_from_db()

        self.assertEqual(
            self.rental.status,
            Rental.Status.CANCELLED,
        )

        self.assertEqual(
            response.data["outstanding_balance"],
            "0.00",
        )

        self.assertEqual(
            Rental.objects.count(),
            1,
        )

    def test_cancellation_releases_reserved_stock(self):
        before = available_quantity(
            self.product,
            self.rental.start_date,
            self.rental.end_date,
        )

        self.assertEqual(before, 70)

        response = self.cancel()

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        after = available_quantity(
            self.product,
            self.rental.start_date,
            self.rental.end_date,
        )

        self.assertEqual(after, 100)

    def test_paid_rental_cannot_be_cancelled(self):
        self.pay("500.00")

        response = self.cancel()

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.rental.refresh_from_db()

        self.assertEqual(
            self.rental.status,
            Rental.Status.BOOKED,
        )

    def test_active_rental_cannot_be_cancelled(self):
        self.dispatch()

        response = self.cancel()

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_cancelled_rental_rejects_payments(self):
        self.cancel()

        response = self.pay("500.00")

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(Payment.objects.count(), 0)

    def test_duplicate_cancellation_is_rejected(self):
        self.cancel()

        response = self.cancel()

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    
    def test_booked_rental_cannot_be_completed(self):
        self.pay("1800.00")

        response = self.complete()

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_fully_paid_but_unreturned_rental(self):
        self.dispatch()
        self.pay("1800.00")

        response = self.complete()

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_fully_returned_but_unpaid_rental(self):
        self.dispatch()
        self.return_all()

        response = self.complete()

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.rental.refresh_from_db()

        self.assertEqual(
            self.rental.status,
            Rental.Status.ACTIVE,
        )

    def test_complete_full_rental_workflow(self):
        self.pay("500.00")
        self.dispatch()
        self.return_all()

        payment_response = self.pay("1300.00")

        self.assertEqual(
            payment_response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertTrue(
            payment_response.data["can_complete"]
        )

        response = self.complete()

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["status"],
            Rental.Status.COMPLETED,
        )

        self.assertEqual(
            response.data["outstanding_quantity"],
            0,
        )

        self.assertEqual(
            response.data["outstanding_balance"],
            "0.00",
        )

        self.assertFalse(
            response.data["can_complete"]
        )

    def test_completed_rental_is_read_only(self):
        self.dispatch()
        self.return_all()
        self.pay("1800.00")

        completed = self.complete()

        self.assertEqual(
            completed.status_code,
            status.HTTP_200_OK,
        )

        responses = [
            self.pay("100.00"),
            self.cancel(),
            self.complete(),
            self.dispatch(),
            self.return_all(),
        ]

        for response in responses:
            self.assertEqual(
                response.status_code,
                status.HTTP_400_BAD_REQUEST,
            )

        self.rental.refresh_from_db()

        self.assertEqual(
            self.rental.status,
            Rental.Status.COMPLETED,
        )

        self.assertEqual(Payment.objects.count(), 1)

    
    
    def test_other_shop_cannot_modify_rental(self):
        other_owner = User.objects.create_user(
            email="other-settlement@example.com",
            password="ExampleSecurePassword123!",
        )

        Shop.objects.create(
            name="Other Shop",
            owner=other_owner,
        )

        self.client.force_authenticate(
            user=other_owner
        )

        responses = [
            self.pay("500.00"),
            self.cancel(),
            self.complete(),
        ]

        for response in responses:
            self.assertEqual(
                response.status_code,
                status.HTTP_404_NOT_FOUND,
            )

        self.assertEqual(Payment.objects.count(), 0)

        self.rental.refresh_from_db()

        self.assertEqual(
            self.rental.status,
            Rental.Status.BOOKED,
        )

    def test_unauthenticated_operations_are_rejected(self):
        self.client.force_authenticate(user=None)

        responses = [
            self.pay("500.00"),
            self.cancel(),
            self.complete(),
        ]

        for response in responses:
            self.assertEqual(
                response.status_code,
                status.HTTP_401_UNAUTHORIZED,
            )

