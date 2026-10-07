from django.contrib import admin

from .models import (
    Category, Coupon, InventoryMovement, Order, OrderItem, OrderStatusHistory, Payment, Product,
    ProductVariant, Review, Shipment,
)


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "brand", "price", "stock", "active", "featured")
    list_filter = ("active", "featured", "category", "brand")
    search_fields = ("name", "sku", "brand", "description")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ProductVariantInline]


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "parent", "image", "active")
    list_filter = ("active",)
    prepopulated_fields = {"slug": ("name",)}


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product", "variant", "product_name", "variant_name", "quantity", "price")


class OrderHistoryInline(admin.TabularInline):
    model = OrderStatusHistory
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "full_name", "total", "payment_status", "status", "created_at")
    list_filter = ("status", "payment_status", "created_at")
    search_fields = ("id", "public_id", "full_name", "email", "phone")
    readonly_fields = ("public_id", "subtotal", "discount", "total", "created_at", "updated_at")
    inlines = [OrderItemInline, OrderHistoryInline]

    def save_model(self, request, obj, form, change):
        previous_status = None
        if change:
            previous_status = Order.objects.filter(pk=obj.pk).values_list("status", flat=True).first()
        super().save_model(request, obj, form, change)
        if previous_status != obj.status:
            OrderStatusHistory.objects.create(
                order=obj, status=obj.status, note=f"Updated by {request.user.username}",
            )


admin.site.register(Coupon)
admin.site.register(Payment)
admin.site.register(Shipment)
admin.site.register(Review)
admin.site.register(InventoryMovement)
