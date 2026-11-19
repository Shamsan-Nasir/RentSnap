
from rest_framework.permissions import BasePermission

from .models import Shop, ShopStaff


class IsShopOwner(BasePermission):
    message = "Only the shop owner can perform this action."

    def has_permission(self, request, view):
        user = request.user

        if not user.is_authenticated:
            return False

        return Shop.objects.filter(
            owner_id=user.pk
        ).exists()


class IsShopMember(BasePermission):
    message = "You must belong to a shop."

    def has_permission(self, request, view):
        user = request.user

        if not user.is_authenticated:
            return False

        owns_shop = Shop.objects.filter(
            owner_id=user.pk
        ).exists()

        staff_member = ShopStaff.objects.filter(
            user_id=user.pk
        ).exists()

        return owns_shop or staff_member
