from django.contrib import admin

from .models import Coupon, Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    readonly_fields = (
        "watch",
        "product_name",
        "sku",
        "unit_price",
        "quantity",
        "total_price",
    )

    def has_add_permission(self, request, obj=None) -> bool:
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("order_number", "user", "status", "total", "created_at")
    list_filter = ("status",)
    search_fields = ("order_number", "user__email", "shipping_full_name")
    list_select_related = ("user",)
    readonly_fields = (
        "user",
        "order_number",
        "status",
        "subtotal",
        "discount",
        "coupon_code",
        "shipping_cost",
        "total",
        "shipping_full_name",
        "shipping_phone",
        "shipping_province",
        "shipping_city",
        "shipping_postal_code",
        "shipping_address_line",
        "created_at",
        "updated_at",
    )
    inlines = (OrderItemInline,)

    def has_add_permission(self, request) -> bool:
        return False


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "discount_type",
        "value",
        "minimum_order",
        "is_active",
        "valid_from",
        "valid_until",
    )
    list_filter = ("discount_type", "is_active")
    search_fields = ("code",)
    readonly_fields = ("created_at", "updated_at")
