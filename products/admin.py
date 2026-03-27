from django.contrib import admin
from .models import (
    Category, Product, ProductMedia,
    ProductAttribute, ProductVariant, VariantAttributeValue,
)


class ProductMediaInline(admin.TabularInline):
    model = ProductMedia
    extra = 0
    fields = ('media_type', 'file', 'alt_text', 'order')
    readonly_fields = ('created_at',)


class ProductAttributeInline(admin.TabularInline):
    model = ProductAttribute
    extra = 0
    autocomplete_fields = ('attribute',)


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0
    fields = ('sku', 'price', 'compare_at_price', 'stock', 'is_active')
    readonly_fields = ('created_at',)


class VariantAttributeValueInline(admin.TabularInline):
    model = VariantAttributeValue
    extra = 0
    autocomplete_fields = ('attribute_value',)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'store', 'parent', 'level', 'is_active', 'created_at')
    list_filter = ('is_active', 'level', 'store')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    list_select_related = ('store', 'parent')


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'sku', 'store', 'category', 'product_type', 'price', 'stock', 'is_active', 'is_featured')
    list_filter = ('product_type', 'is_active', 'is_featured', 'store')
    search_fields = ('name', 'sku')
    list_select_related = ('store', 'category')
    inlines = [ProductMediaInline, ProductAttributeInline, ProductVariantInline]

    fieldsets = (
        ('Basic Info', {
            'fields': ('store', 'category', 'name', 'sku', 'product_type'),
        }),
        ('Pricing & Stock', {
            'fields': ('price', 'compare_at_price', 'stock'),
        }),
        ('Status', {
            'fields': ('is_active', 'is_featured'),
        }),
    )


@admin.register(ProductMedia)
class ProductMediaAdmin(admin.ModelAdmin):
    list_display = ('product', 'media_type', 'alt_text', 'order', 'created_at')
    list_filter = ('media_type',)
    search_fields = ('product__name', 'alt_text')
    list_select_related = ('product',)


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ('sku', 'product', 'price', 'stock', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('sku', 'product__name')
    list_select_related = ('product',)
    inlines = [VariantAttributeValueInline]
