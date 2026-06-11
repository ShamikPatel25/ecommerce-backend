from django.contrib import admin
from .models import Store

@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ['name', 'subdomain', 'owner', 'is_active', 'created_at']
    list_filter = ['is_active', 'currency', 'created_at']
    search_fields = ['name', 'subdomain', 'owner__email']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('name', 'subdomain', 'owner', 'description')
        }),
        ('Settings', {
            'fields': ('currency', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)  
        }),
    )