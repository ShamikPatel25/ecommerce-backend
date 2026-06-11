import uuid
from django.db import models
from apps.tenants.models import Store
from apps.products.models import Category

class Attribute(models.Model):
    """
    Attribute Definition (e.g., Size, Color, Material)

    Examples:
    - Category: Clothes → Attribute: Size
    - Category: Clothes → Attribute: Color
    - Category: Electronics → Attribute: Storage

    IMPORTANT: One attribute belongs to ONE category
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name='attributes'
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='attributes',
        help_text='Which category this attribute belongs to'
    )
    name = models.CharField(
        max_length=100,
        help_text='Attribute name (e.g., Size, Color, Material)'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['category', 'name']
        unique_together = ['store', 'category', 'name']  
        verbose_name = 'Attribute'
        verbose_name_plural = 'Attributes'
    
    def __str__(self):
        return f"{self.category.name} → {self.name}"


class AttributeValue(models.Model):
    """
    Attribute Values (e.g., Size: 30, 40, 42, 46)

    Examples:
    - Attribute: Size → Values: 30, 40, 42, 46
    - Attribute: Color → Values: Red, Blue, Black
    - Attribute: Storage → Values: 128GB, 256GB, 512GB

    WORKFLOW:
    1. Create Attribute: Clothes → Size
    2. Add Values: 30, 40, 42, 46 (one by one)
    3. Create Another Attribute: Clothes → Color
    4. Add Values: Red, Blue, Black (one by one)
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    attribute = models.ForeignKey(
        Attribute,
        on_delete=models.CASCADE,
        related_name='values',
        help_text='Which attribute this value belongs to'
    )
    value = models.CharField(
        max_length=100,
        help_text='Attribute value (e.g., 30, Red, 128GB)'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['attribute', 'value']
        unique_together = ['attribute', 'value']  # No duplicate values per attribute
        verbose_name = 'Attribute Value'
        verbose_name_plural = 'Attribute Values'
    
    def __str__(self):
        return f"{self.attribute.name}: {self.value}"