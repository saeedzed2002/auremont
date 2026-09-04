from django import forms

from apps.accounts.models import Address


class CheckoutAddressForm(forms.Form):
    saved_address = forms.ChoiceField(
        choices=(),
        required=False,
        label="Saved address",
    )
    full_name = forms.CharField(max_length=255, required=False, label="Recipient name")
    phone = forms.CharField(max_length=32, required=False, label="Phone number")
    province = forms.CharField(max_length=100, required=False, label="Province / state")
    city = forms.CharField(max_length=100, required=False, label="City")
    postal_code = forms.CharField(max_length=20, required=False, label="Postal code")
    address_line = forms.CharField(
        required=False,
        label="Address",
        widget=forms.Textarea(attrs={"rows": 4}),
    )

    def __init__(self, *args, user, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.addresses = user.addresses.all()
        self.fields["saved_address"].choices = [("", "Enter a new address")] + [
            (
                str(address.pk),
                f"{address.full_name} — {address.city}, {address.province}",
            )
            for address in self.addresses
        ]
        if not self.is_bound:
            default_address = next(
                (address for address in self.addresses if address.is_default),
                None,
            )
            if default_address:
                self.initial["saved_address"] = str(default_address.pk)

    def clean(self):
        cleaned_data = super().clean()
        saved_address_id = cleaned_data.get("saved_address")
        if saved_address_id:
            self.selected_address = self.addresses.filter(pk=saved_address_id).first()
            if self.selected_address is None:
                self.add_error("saved_address", "Choose one of your saved addresses.")
            return cleaned_data

        self.selected_address = None
        for field_name in (
            "full_name",
            "phone",
            "province",
            "city",
            "postal_code",
            "address_line",
        ):
            if not cleaned_data.get(field_name, "").strip():
                self.add_error(field_name, "This field is required for a new address.")
        return cleaned_data

    def shipping_address(self) -> dict[str, str]:
        if self.selected_address:
            return shipping_address_from_address(self.selected_address)

        return {
            "full_name": self.cleaned_data["full_name"].strip(),
            "phone": self.cleaned_data["phone"].strip(),
            "province": self.cleaned_data["province"].strip(),
            "city": self.cleaned_data["city"].strip(),
            "postal_code": self.cleaned_data["postal_code"].strip(),
            "address_line": self.cleaned_data["address_line"].strip(),
        }


def shipping_address_from_address(address: Address) -> dict[str, str]:
    return {
        "full_name": address.full_name,
        "phone": address.phone,
        "province": address.province,
        "city": address.city,
        "postal_code": address.postal_code,
        "address_line": address.address_line,
    }
