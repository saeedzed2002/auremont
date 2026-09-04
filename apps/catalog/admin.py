from django.contrib import admin

from .models import Brand, Category, Collection, Review, Watch, WatchImage


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


class WatchImageInline(admin.TabularInline):
    model = WatchImage
    extra = 1
    fields = ("image", "alt_text", "position", "is_primary")


@admin.register(Watch)
class WatchAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "brand",
        "category",
        "current_price",
        "stock",
        "is_active",
        "is_featured",
    )
    list_filter = (
        "is_active",
        "is_featured",
        "brand",
        "category",
        "movement",
        "gender",
    )
    list_select_related = ("brand", "category")
    search_fields = ("name", "sku", "brand__name")
    prepopulated_fields = {"slug": ("name",)}
    filter_horizontal = ("collections",)
    readonly_fields = ("created_at", "updated_at")
    inlines = (WatchImageInline,)

    @admin.display(ordering="price", description="Current price")
    def current_price(self, obj: Watch):
        return obj.current_price


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = (
        "watch",
        "user",
        "rating",
        "moderation_status",
        "is_verified_purchase",
        "created_at",
    )
    list_filter = ("moderation_status", "rating", "is_verified_purchase")
    search_fields = ("watch__name", "watch__sku", "user__email", "comment")
    list_select_related = ("watch", "user")
    readonly_fields = (
        "user",
        "watch",
        "rating",
        "comment",
        "is_verified_purchase",
        "created_at",
        "updated_at",
    )
    fields = (*readonly_fields, "moderation_status")
