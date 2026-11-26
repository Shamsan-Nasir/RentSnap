
from django import forms
from django_filters import rest_framework as filters

from .models import Rental


class RentalFilterForm(forms.Form):

    def clean(self):
        cleaned_data = super().clean()

        due_from = cleaned_data.get("due_from")
        due_to = cleaned_data.get("due_to")

        if due_from and due_to and due_from > due_to:
            self.add_error(
                "due_to",
                "End of filter range must not "
                "be before its start.",
            )

        return cleaned_data


class RentalFilter(filters.FilterSet):

    status = filters.ChoiceFilter(
        choices=Rental.Status.choices,
    )

    customer_id = filters.NumberFilter(
        field_name="customer_id",
        lookup_expr="exact",
        min_value=1,
    )

    due_from = filters.DateFilter(
        field_name="end_date",
        lookup_expr="gte",
    )

    due_to = filters.DateFilter(
        field_name="end_date",
        lookup_expr="lte",
    )

    class Meta:
        model = Rental

        form = RentalFilterForm

        fields = [
            "status",
            "customer_id",
            "due_from",
            "due_to",
        ]
