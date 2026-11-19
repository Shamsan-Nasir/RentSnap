
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from rest_framework.exceptions import ValidationError

from .models import Shop, ShopStaff


User = get_user_model()


def get_user_shop(user):
    if not user.is_authenticated:
        return None

    shop = Shop.objects.filter(owner_id=user.pk).first()

    if shop is not None:
        return shop

    membership = (
        ShopStaff.objects
        .select_related("shop")
        .filter(user_id=user.pk)
        .first()
    )

    if membership is not None:
        return membership.shop

    return None


def create_shop_for_user(user, name):
    try:
        with transaction.atomic():
            User.objects.select_for_update().get(pk=user.pk)

            already_owner = Shop.objects.filter(
                owner_id=user.pk
            ).exists()

            already_staff = ShopStaff.objects.filter(
                user_id=user.pk
            ).exists()

            if already_owner or already_staff:
                raise ValidationError({
                    "detail": "You already belong to a shop."
                })

            return Shop.objects.create(
                owner=user,
                name=name,
            )

    except IntegrityError:
        raise ValidationError({
            "detail": "Could not create shop due to a membership conflict."
        })


def assign_existing_staff(shop, email):
    email = email.strip().lower()

    try:
        with transaction.atomic():
            user = (
                User.objects
                .select_for_update()
                .filter(email=email)
                .first()
            )

            if user is None:
                raise ValidationError({
                    "email": "No registered user has this email."
                })

            owns_shop = Shop.objects.filter(
                owner_id=user.pk
            ).exists()

            already_staff = ShopStaff.objects.filter(
                user_id=user.pk
            ).exists()

            if owns_shop or already_staff:
                raise ValidationError({
                    "email": "This user already belongs to a shop."
                })

            return ShopStaff.objects.create(
                shop=shop,
                user=user,
            )

    except IntegrityError:
        raise ValidationError({
            "email": "This user already has a shop membership."
        })
