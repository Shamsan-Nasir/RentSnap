
from django.conf import settings
from django.db import models


class Shop(models.Model):
    name = models.CharField(max_length=150)

    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_shop",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class ShopStaff(models.Model):
    shop = models.ForeignKey(
        Shop,
        on_delete=models.PROTECT,
        related_name="staff_members",
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="shop_staff_membership",
    )

    added_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} - {self.shop.name}"
