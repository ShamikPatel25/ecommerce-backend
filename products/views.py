from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction, models
from itertools import product as itertools_product

from .models import (
    Category, Product, ProductMedia, ProductAttribute, 
    ProductVariant, VariantAttributeValue
)
from .serializers import (
    CategorySerializer, CategoryTreeSerializer,
    ProductSerializer, ProductCreateSerializer, ProductMediaSerializer,
    GenerateCatalogRequestSerializer, ProductVariantSerializer
)
from attributes.models import Attribute, AttributeValue
from tenants.utils import get_tenant_model


@extend_schema(tags=['Categories'])
@extend_schema_view(
    list=extend_schema(summary="List all categories"),
    create=extend_schema(summary="Create new category"),
    retrieve=extend_schema(summary="Get category details"),
    update=extend_schema(summary="Update category"),
    destroy=extend_schema(summary="Delete category")
)
class CategoryViewSet(viewsets.ModelViewSet):
    """Category Management with Nested Support"""
    permission_classes = [IsAuthenticated]
    pagination_class = None
    
    def get_serializer_class(self):
        if self.action == 'tree':
            return CategoryTreeSerializer
        return CategorySerializer
    
    def get_queryset(self):
        return get_tenant_model(self.request, Category)
    
    def perform_create(self, serializer):
        serializer.save(store=self.request.tenant)
    
    @extend_schema(
        summary="Get category tree",
        description="Get nested category structure"
    )
    @action(detail=False, methods=['get'])
    def tree(self, request):
        """Get category tree (only root categories with children)"""
        root_categories = self.get_queryset().filter(parent=None)
        serializer = CategoryTreeSerializer(root_categories, many=True)
        return Response(serializer.data)

    @extend_schema(summary="Toggle category active status")
    @action(detail=True, methods=['post'])
    def toggle_active(self, request, pk=None):
        """Toggle is_active and cascade to all products in this category"""
        category = self.get_object()
        category.is_active = not category.is_active
        category.save()
        # Cascade: activate/deactivate all products in this category
        category.products.update(is_active=category.is_active)
        return Response(CategorySerializer(category).data)


@extend_schema(tags=['Products'])
@extend_schema_view(
    list=extend_schema(summary="List all products"),
    create=extend_schema(summary="Create new product"),
    retrieve=extend_schema(summary="Get product details"),
    update=extend_schema(summary="Update product"),
    destroy=extend_schema(summary="Delete product")
)
class ProductViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    pagination_class = None

    """
    Complete Product Management with Catalog Generation
    """    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ProductCreateSerializer
        return ProductSerializer
    
    def get_queryset(self):
        qs = get_tenant_model(self.request, Product).prefetch_related('media', 'variants')
        params = self.request.query_params

        # Search by name or SKU
        search = params.get('search', '').strip()
        if search:
            qs = qs.filter(
                models.Q(name__icontains=search) | models.Q(sku__icontains=search)
            )

        # Filter by category
        category = params.get('category')
        if category:
            qs = qs.filter(category_id=category)

        # Filter by product type
        product_type = params.get('product_type')
        if product_type in ('single', 'catalog'):
            qs = qs.filter(product_type=product_type)

        # Filter by price range
        min_price = params.get('min_price')
        if min_price:
            qs = qs.filter(price__gte=min_price)
        max_price = params.get('max_price')
        if max_price:
            qs = qs.filter(price__lte=max_price)

        # Filter by stock status
        stock_status = params.get('stock_status')
        if stock_status == 'in_stock':
            qs = qs.filter(stock__gt=0)
        elif stock_status == 'out_of_stock':
            qs = qs.filter(stock=0)

        # Filter by active status
        is_active = params.get('is_active')
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() in ('true', '1'))

        return qs
    
    def perform_create(self, serializer):
        serializer.save(store=self.request.tenant)

    @extend_schema(
        summary="Check if SKU already exists",
        description="Returns whether a SKU is already taken"
    )
    @action(detail=False, methods=['post'])
    def check_sku(self, request):
        sku = request.data.get('sku', '').strip().upper()
        if not sku:
            return Response({'exists': False})
        exists = Product.objects.filter(sku=sku).exists()
        return Response({'exists': exists})

    @extend_schema(
        summary="Upload product media",
        description="Upload images or videos for product"
    )
    @action(detail=True, methods=['post'])
    def upload_media(self, request, pk=None):
        """
        Upload product media
        
        POST /api/products/{id}/upload_media/
        Form-data:
        - media_type: image or video
        - file: uploaded file
        - alt_text: (optional)
        - order: (optional)
        """
        product = self.get_object()
        
        media_type = request.data.get('media_type')
        file = request.FILES.get('file')
        
        if not media_type or not file:
            return Response(
                {'error': 'media_type and file are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        media = ProductMedia.objects.create(
            product=product,
            media_type=media_type,
            file=file,
            alt_text=request.data.get('alt_text', ''),
            order=request.data.get('order', 0)
        )
        
        serializer = ProductMediaSerializer(media, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @extend_schema(
        summary="Select attributes for catalog",
        description="Select which attributes to use for this catalog product"
    )
    @action(detail=True, methods=['post'])
    def select_attributes(self, request, pk=None):
        """
        Select attributes for catalog product
        
        POST /api/products/{id}/select_attributes/
        Body: {
            "attribute_ids": [1, 2]  // e.g., Size and Color
        }
        """
        product = self.get_object()
        
        if product.product_type != 'catalog':
            return Response(
                {'error': 'This action is only for catalog products'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        attribute_ids = request.data.get('attribute_ids', [])
        
        if not attribute_ids:
            return Response(
                {'error': 'attribute_ids is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate attributes belong to same category
        attributes = Attribute.objects.filter(
            id__in=attribute_ids,
            store=request.tenant
        )
        
        if attributes.count() != len(attribute_ids):
            return Response(
                {'error': 'Some attributes not found'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check all attributes belong to product category
        for attr in attributes:
            if attr.category != product.category:
                return Response(
                    {'error': f'Attribute "{attr.name}" does not belong to category "{product.category.name}"'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Clear existing selections
        product.selected_attributes.all().delete()
        
        # Create new selections
        for attr in attributes:
            ProductAttribute.objects.create(product=product, attribute=attr)
        
        # Return updated product with attributes
        serializer = ProductSerializer(product, context={'request': request})
        return Response({
            'message': f'Selected {len(attribute_ids)} attributes',
            'product': serializer.data
        })
    
    @extend_schema(
        summary="Generate catalog variants",
        description="Generate product variants based on selected attributes",
        request=GenerateCatalogRequestSerializer
    )
    @action(detail=True, methods=['post'])
    def generate_catalog(self, request, pk=None):
        """
        Generate Catalog Variants
        
        POST /api/products/{id}/generate_catalog/
        
        Body for SINGLE CATALOG (Radio Button):
        {
            "single_catalog_mode": true,
            "selected_combinations": [
                {
                    "attribute_values": [1, 5]  // Size: 40, Color: Black
                }
            ]
        }
        
        Body for MULTIPLE CATALOGS (Checkbox):
        {
            "single_catalog_mode": false,
            "selected_combinations": [
                {
                    "attribute_values": [1, 5]  // Size: 40, Color: Black
                },
                {
                    "attribute_values": [1, 6]  // Size: 40, Color: Blue
                },
                {
                    "attribute_values": [2, 5]  // Size: 42, Color: Black
                }
            ]
        }
        
        AUTO-GENERATE ALL (Pass empty to generate all combinations):
        {
            "single_catalog_mode": false,
            "selected_combinations": []  // Will auto-generate all combinations
        }
        """
        product = self.get_object()
        
        if product.product_type != 'catalog':
            return Response(
                {'error': 'This action is only for catalog products'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not product.selected_attributes.exists():
            return Response(
                {'error': 'Please select attributes first using /select_attributes/'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = GenerateCatalogRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        single_catalog_mode = serializer.validated_data['single_catalog_mode']
        selected_combinations = serializer.validated_data['selected_combinations']
        
        # If no combinations provided, auto-generate all
        if not selected_combinations:
            selected_combinations = self._generate_all_combinations(product)
        
        # Validate single catalog mode
        if single_catalog_mode and len(selected_combinations) > 1:
            return Response(
                {'error': 'Single catalog mode allows only one combination'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Generate variants
        try:
            with transaction.atomic():
                created_variants = []
                skipped_variants = []

                for combo in selected_combinations:
                    variant, created = self._create_variant(
                        product,
                        combo['attribute_values'],
                        price=combo.get('price'),
                        stock=combo.get('stock', 0),
                    )
                    if created:
                        created_variants.append(variant)
                    else:
                        skipped_variants.append(variant)

                return Response({
                    'message': f'Generated {len(created_variants)} new variant(s), skipped {len(skipped_variants)} duplicate(s)',
                    'mode': 'Single Catalog' if single_catalog_mode else 'Multiple Catalogs',
                    'variants': ProductVariantSerializer(created_variants, many=True).data
                }, status=status.HTTP_201_CREATED)
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @extend_schema(summary="Update a single catalog variant")
    @action(detail=True, methods=['patch'], url_path='variants/(?P<variant_id>[^/.]+)')
    def update_variant(self, request, pk=None, variant_id=None):
        """
        Update stock and/or price of a single variant.
        PATCH /api/products/{id}/variants/{variant_id}/
        Body: { "stock": 10, "price": 999.00 }
        """
        product = self.get_object()
        try:
            variant = product.variants.get(id=variant_id)
        except ProductVariant.DoesNotExist:
            return Response({'error': 'Variant not found'}, status=status.HTTP_404_NOT_FOUND)

        stock = request.data.get('stock')
        price = request.data.get('price')

        if stock is not None:
            variant.stock = int(stock)
        if price is not None:
            variant.price = price if price != '' else None
        variant.save()

        return Response(ProductVariantSerializer(variant).data)

    @extend_schema(summary="Delete a single catalog variant")
    @action(detail=True, methods=['delete'], url_path='variants/(?P<variant_id>[^/.]+)/delete')
    def delete_variant(self, request, pk=None, variant_id=None):
        """
        Delete a single variant.
        DELETE /api/products/{id}/variants/{variant_id}/delete/
        """
        product = self.get_object()
        try:
            variant = product.variants.get(id=variant_id)
        except ProductVariant.DoesNotExist:
            return Response({'error': 'Variant not found'}, status=status.HTTP_404_NOT_FOUND)

        variant.delete()
        return Response({'message': 'Variant deleted'}, status=status.HTTP_204_NO_CONTENT)

    def _generate_all_combinations(self, product):
        """Auto-generate all possible combinations from selected attributes"""
        selected_attrs = product.selected_attributes.all()
        
        # Get all values for each attribute
        attribute_values_list = []
        for prod_attr in selected_attrs:
            values = list(prod_attr.attribute.values.values_list('id', flat=True))
            attribute_values_list.append(values)
        
        # Generate cartesian product (all combinations)
        all_combinations = list(itertools_product(*attribute_values_list))
        
        # Format as required
        formatted_combinations = []
        for combo in all_combinations:
            formatted_combinations.append({
                'attribute_values': list(combo)
            })
        
        return formatted_combinations
    
    def _create_variant(self, product, attribute_value_ids, price=None, stock=0):
        """Create a single variant. Returns (variant, created) — skips if duplicate SKU exists."""
        # Validate attribute values
        attr_values = AttributeValue.objects.filter(id__in=attribute_value_ids)

        if attr_values.count() != len(attribute_value_ids):
            raise ValueError('Some attribute values not found')

        # Generate deterministic SKU from product SKU + attribute values
        sku_parts = [product.sku]
        for av in attr_values:
            sku_parts.append(av.value.replace(' ', '-'))
        variant_sku = '-'.join(sku_parts)

        # Skip if this exact variant already exists
        existing = ProductVariant.objects.filter(product=product, sku=variant_sku).first()
        if existing:
            return existing, False  # (variant, created=False)

        # Create the new variant
        variant = ProductVariant.objects.create(
            product=product,
            sku=variant_sku,
            price=price if price is not None else None,  # None = use product base price
            stock=int(stock) if stock else 0,
            is_active=True
        )

        # Link attribute values to variant
        for av in attr_values:
            VariantAttributeValue.objects.create(
                variant=variant,
                attribute_value=av
            )

        return variant, True  # (variant, created=True)
    
    @extend_schema(
        summary="Get available attributes for catalog",
        description="Get attributes that can be used for this product based on category"
    )
    @action(detail=True, methods=['get'])
    def available_attributes(self, request, pk=None):
        """
        Get available attributes for this product
        
        GET /api/products/{id}/available_attributes/
        """
        product = self.get_object()
        
        if not product.category:
            return Response(
                {'error': 'Product must have a category'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from attributes.serializers import AttributeSerializer
        
        # Get all attributes for this category
        attributes = Attribute.objects.filter(
            category=product.category,
            store=request.tenant
        ).prefetch_related('values')
        
        serializer = AttributeSerializer(attributes, many=True)
        
        return Response({
            'category': product.category.full_path,
            'available_attributes': serializer.data
        })