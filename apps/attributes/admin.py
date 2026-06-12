from django.contrib import admin
from .models import Attribute, AttributeValue

class AttributeValueInline(admin.TabularInline):
    model = AttributeValue
    extra = 1

@admin.register(Attribute)
class AttributeAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'values_count', 'created_at']
    list_filter = ['category', 'created_at']
    search_fields = ['name', 'category__name']
    inlines = [AttributeValueInline]
    
    def values_count(self, obj):
        return obj.values.count()
    values_count.short_description = 'Values Count'

@admin.register(AttributeValue)
class AttributeValueAdmin(admin.ModelAdmin):
    list_display = ['value', 'attribute', 'created_at']
    list_filter = ['attribute', 'created_at']
    search_fields = ['value', 'attribute__name']