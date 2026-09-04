from django import forms


class ReviewForm(forms.Form):
    RATING_CHOICES = tuple((score, f"{score} out of 5") for score in range(1, 6))

    rating = forms.TypedChoiceField(
        choices=RATING_CHOICES,
        coerce=int,
        label="Rating",
        widget=forms.Select(
            attrs={
                "class": (
                    "mt-2 block w-full border border-charcoal/25 bg-ivory px-3 py-3 "
                    "text-sm text-charcoal outline-none focus:border-brass "
                    "focus:ring-1 focus:ring-brass"
                )
            }
        ),
    )
    comment = forms.CharField(
        label="Your review",
        widget=forms.Textarea(
            attrs={
                "rows": 5,
                "class": (
                    "mt-2 block w-full border border-charcoal/25 bg-ivory px-3 py-3 "
                    "text-sm leading-6 text-charcoal outline-none focus:border-brass "
                    "focus:ring-1 focus:ring-brass"
                ),
            }
        ),
    )

    def clean_comment(self) -> str:
        return self.cleaned_data["comment"].strip()
