import uuid
from django.db import models
from django.conf import settings
from django.core.validators import RegexValidator
from django_tenants.models import TenantMixin, DomainMixin

class Store(TenantMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Subdomain validator - allows lowercase letters, numbers, and underscores
    subdomain_validator = RegexValidator(
        regex=r'^[a-z0-9_]+$',
        message='Subdomain can only contain lowercase letters, numbers, and underscores'
    )
    
    name = models.CharField(
        max_length=100,
        help_text='Store display name (e.g., "Nike Official Store")'
    )
    
    subdomain = models.SlugField(
        max_length=50,
        unique=True,
        validators=[subdomain_validator],
        help_text='Unique subdomain (e.g., "nike" for nike.myplatform.com)'
    )
    
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='owned_stores',
        help_text='User who created/owns this store',
        null=True, blank=True
    )
    
    # Store Settings
    description = models.TextField(blank=True)
    is_active = models.BooleanField(
        default=True,
        help_text='Inactive stores are inaccessible to customers'
    )
    
    currency = models.CharField(
        max_length=3,
        default='INR',
        choices=[
            ('INR', 'Indian Rupee'),
            ('USD', 'US Dollar'),
            ('EUR', 'Euro'),
            ('GBP', 'British Pound'),
        ]
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # default true, schema will be automatically created and synced when it is saved
    auto_create_schema = True
    auto_drop_schema = True
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Store'
        verbose_name_plural = 'Stores'
        indexes = [
            models.Index(fields=['is_active', 'created_at']),
        ]
    
    def save(self, *args, **kwargs):
        is_new = self._state.adding
        if not self.schema_name:
            self.schema_name = self.subdomain
            
        super().save(*args, **kwargs)
        
        # Auto-create the domain for the store
        if is_new:
            from apps.tenants.models import Domain
            if settings.DEBUG:
                domain_name = f"{self.subdomain}.localhost"
            else:
                from decouple import config
                domain = config('DOMAIN', default='myplatform.com')
                domain_name = f"{self.subdomain}.{domain}"
                
            Domain.objects.get_or_create(
                domain=domain_name,
                tenant=self,
                is_primary=True
            )
    
    def __str__(self):
        return f"{self.name} ({self.subdomain})"
    
    def get_full_domain(self):
        """Returns full domain based on environment."""
        if settings.DEBUG:
            return f"{self.subdomain}.localhost:3000"
        from decouple import config
        domain = config('DOMAIN', default='myplatform.com')
        return f"{self.subdomain}.{domain}"

class Domain(DomainMixin):
    pass