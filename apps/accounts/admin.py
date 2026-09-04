from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from .models import Address, User


class AddressInline(admin.TabularInline):
    model = Address
    extra = 0
    fields = ("full_name", "city", "province", "postal_code", "is_default")
    readonly_fields = ("created_at", "updated_at")


@admin.register(User)
class AuremontUserAdmin(UserAdmin):
    ordering = ("email",)
    list_display = ("email", "full_name", "is_staff", "is_active")
    list_filter = ("is_staff", "is_superuser", "is_active")
    search_fields = ("email", "full_name")
    inlines = (AddressInline,)

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Personal info"), {"fields": ("full_name",)}),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "full_name", "password1", "password2"),
            },
        ),
    )


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ("full_name", "user", "city", "province", "is_default")
    list_filter = ("is_default", "province")
    search_fields = ("full_name", "user__email", "city", "postal_code")
    list_select_related = ("user",)
