from django import forms


class CartQuantityForm(forms.Form):
    quantity = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(
            attrs={
                "min": 1,
                "step": 1,
                "class": (
                    "w-16 border border-charcoal/25 bg-ivory px-2 py-2 text-center "
                    "text-sm text-charcoal outline-none focus:border-brass "
                    "focus:ring-1 focus:ring-brass"
                ),
            }
        ),
    )
