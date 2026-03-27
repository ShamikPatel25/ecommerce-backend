from django.db import models
from tenants.models import Store

class Category(models.Model):
    """
    Nested Categories System (Up to 3 Levels)
    
    Examples:
    Level 1: Electronics (parent=None)
    Level 2: Smartphones (parent=Electronics)
    Level 3: Android (parent=Smartphones)
    """
    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name='categories'
    )
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100)
    
    # Nested categories
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children'
    )
    
    # Level tracking (auto-calculated)
    level = models.PositiveIntegerField(default=0, editable=False)

    # Status
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['level', 'name']
        unique_together = ['store', 'slug']
    
    def save(self, *args, **kwargs):
        """Auto-calculate level based on parent"""
        if self.parent:
            self.level = self.parent.level + 1
        else:
            self.level = 0
        super().save(*args, **kwargs)
    
    def __str__(self):
        if self.parent:
            return f"{self.parent.name} > {self.name}"
        return self.name
    
    @property
    def full_path(self):
        """Get full category path (e.g., Electronics > Smartphones > Android)"""
        path = [self.name]
        parent = self.parent
        while parent:
            path.insert(0, parent.name)
            parent = parent.parent
        return " > ".join(path)


class ProductType(models.TextChoices):
    """Product Types"""
    SINGLE = 'single', 'Single Product'
    CATALOG = 'catalog', 'Catalog (with variants)'


class Product(models.Model):
    """
    Enhanced Product Model with Catalog Support
    """
    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name='products'
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='products'
    )
    
    # Basic Info
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, blank=True)
    sku = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, default='')
    
    # Product Type
    product_type = models.CharField(
        max_length=10,
        choices=ProductType.choices,
        default=ProductType.SINGLE,
        help_text='Single product or Catalog with variants'
    )
    
    # Pricing (for single products or base price for catalog)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text='Price for single product or base price for catalog'
    )
    compare_at_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    # Inventory (for single products only)
    stock = models.PositiveIntegerField(
        default=0,
        help_text='Stock for single products (catalog uses variant stock)'
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['store', 'is_active']),
            models.Index(fields=['sku']),
            models.Index(fields=['product_type']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_product_type_display()})"


class ProductMedia(models.Model):
    """
    Product Photos and Videos
    """
    MEDIA_TYPE_CHOICES = [
        ('image', 'Image'),
        ('video', 'Video'),
    ]
    
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='media'
    )
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPE_CHOICES)
    file = models.FileField(
        upload_to='products/%Y/%m/',
        help_text='Upload image or video'
    )
    alt_text = models.CharField(max_length=200, blank=True)
    order = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['order', 'created_at']
        verbose_name = 'Product Media'
        verbose_name_plural = 'Product Media'
    
    def __str__(self):
        return f"{self.product.name} - {self.media_type}"


class ProductAttribute(models.Model):
    """
    Link between Product and Attributes (Selected Attributes for Catalog)
    
    Example:
    Product: T-Shirt (Catalog)
    Selected Attributes: Size, Color
    """
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='selected_attributes'
    )
    attribute = models.ForeignKey(
        'attributes.Attribute',
        on_delete=models.CASCADE
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['product', 'attribute']
        verbose_name = 'Product Attribute'
        verbose_name_plural = 'Product Attributes'
    
    def __str__(self):
        return f"{self.product.name} - {self.attribute.name}"


class ProductVariant(models.Model):
    """
    Product Variants (Catalog Combinations)
    
    Example:
    Product: T-Shirt
    Variant 1: Size=40, Color=Black
    Variant 2: Size=40, Color=Blue
    Variant 3: Size=42, Color=Black
    """
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='variants'
    )
    
    # Unique SKU for this variant
    sku = models.CharField(max_length=100, unique=True)
    
    # Pricing (can override product base price)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Leave empty to use product base price'
    )
    compare_at_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    # Stock for this variant
    stock = models.PositiveIntegerField(default=0)
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['sku']
        verbose_name = 'Product Variant'
        verbose_name_plural = 'Product Variants'
    
    def __str__(self):
        return f"{self.product.name} - {self.sku}"
    
    @property
    def final_price(self):
        """Get final price (variant price or product base price)"""
        return self.price if self.price else self.product.price
    
    @property
    def attribute_values_display(self):
        """Display all attribute values (e.g., 'Size: 40, Color: Black')"""
        values = self.attribute_values.select_related('attribute_value__attribute')
        return ", ".join([
            f"{av.attribute_value.attribute.name}: {av.attribute_value.value}"
            for av in values
        ])


class VariantAttributeValue(models.Model):
    """
    Links Variant to Attribute Values
    
    Example:
    Variant: T-Shirt-40-Black
    ├── Size: 40
    └── Color: Black
    """
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.CASCADE,
        related_name='attribute_values'
    )
    attribute_value = models.ForeignKey(
        'attributes.AttributeValue',
        on_delete=models.CASCADE
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['variant', 'attribute_value']
        verbose_name = 'Variant Attribute Value'
        verbose_name_plural = 'Variant Attribute Values'
    
    def __str__(self):
        return f"{self.variant.sku} - {self.attribute_value.attribute.name}: {self.attribute_value.value}"