from django import forms

from .models import Address, User


class AuremontSignupForm(forms.Form):
    full_name = forms.CharField(max_length=255, label="Full name")

    def signup(self, request, user):
        user.full_name = self.cleaned_data["full_name"].strip()
        user.save(update_fields=["full_name"])


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("full_name",)
        labels = {"full_name": "Full name"}


class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = (
            "full_name",
            "phone",
            "province",
            "city",
            "postal_code",
            "address_line",
            "is_default",
        )
        labels = {
            "full_name": "Recipient name",
            "phone": "Phone number",
            "province": "Province / state",
            "city": "City",
            "postal_code": "Postal code",
            "address_line": "Address",
            "is_default": "Use as my default address",
        }
        widgets = {
            "address_line": forms.Textarea(attrs={"rows": 4}),
        }

    def clean_postal_code(self) -> str:
        return self.cleaned_data["postal_code"].strip()
