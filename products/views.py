from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction, models
from itertools import product as itertools_product
import logging
import os

logger = logging.getLogger(__name__)

from .models import (
    Category, Product, ProductMedia, ProductAttribute,
    ProductVariant, VariantAttributeValue, ProductType
)
from .serializers import (
    CategorySerializer, CategoryTreeSerializer,
    ProductSerializer, ProductCreateSerializer, ProductMediaSerializer,
    GenerateCatalogRequestSerializer, ProductVariantSerializer,
    StorefrontProductSerializer
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
    """Complete Product Management with Catalog Generation"""
    permission_classes = [IsAuthenticated]
    pagination_class = None

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
        if product_type in (ProductType.SINGLE, ProductType.CATALOG):
            qs = qs.filter(product_type=product_type)

        # Filter by price range
        min_price = params.get('min_price')
        if min_price:
            try:
                qs = qs.filter(price__gte=float(min_price))
            except ValueError:
                pass
        max_price = params.get('max_price')
        if max_price:
            try:
                qs = qs.filter(price__lte=float(max_price))
            except ValueError:
                pass

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
        exists = Product.objects.filter(store=request.tenant, sku=sku).exists()
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
        - attribute_value_id: (optional) link image to a specific attribute value (e.g., Color: Red)

        Auto-detection:
        If no attribute_value_id is provided, the system tries to match the
        filename against existing attribute values for the product.
        E.g., uploading "polo_tshirt_red.webp" for a product with color attribute
        will auto-link to the "Red" value.
        """
        product = self.get_object()

        media_type = request.data.get('media_type')
        file = request.FILES.get('file')

        if not media_type or not file:
            return Response(
                {'error': 'media_type and file are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Resolve attribute value (explicit or auto-detected)
        attribute_value_obj, auto_detected, error_response = self._resolve_attribute_value(
            request, product, file
        )
        if error_response:
            return error_response

        # Generate alt_text
        alt_text = self._generate_alt_text(request, product, attribute_value_obj)

        media = ProductMedia.objects.create(
            product=product,
            media_type=media_type,
            file=file,
            alt_text=alt_text,
            attribute_value=attribute_value_obj,
            order=request.data.get('order', 0),
            is_thumbnail=str(request.data.get('is_thumbnail', 'false')).lower() in ('true', '1'),
        )

        serializer = ProductMediaSerializer(media, context={'request': request})
        response_data = serializer.data
        if auto_detected:
            response_data['auto_detected'] = True
            response_data['auto_detected_label'] = f"{attribute_value_obj.attribute.name}: {attribute_value_obj.value}"
        return Response(response_data, status=status.HTTP_201_CREATED)

    def _resolve_attribute_value(self, request, product, file):
        """Resolve the attribute value from an explicit ID or by auto-detecting from the filename.

        Returns (attribute_value_obj, auto_detected, error_response).
        If error_response is not None, the caller should return it immediately.
        """
        attribute_value_id = request.data.get('attribute_value_id')
        attribute_value_obj = None
        auto_detected = False

        if attribute_value_id:
            try:
                attribute_value_obj = AttributeValue.objects.get(id=attribute_value_id)
            except AttributeValue.DoesNotExist:
                return None, False, Response(
                    {'error': 'Attribute value not found'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            return attribute_value_obj, False, None

        # Auto-detect from filename for catalog products
        if product.product_type == ProductType.CATALOG:
            attribute_value_obj = self._auto_detect_attribute_value(product, file)
            auto_detected = attribute_value_obj is not None

        return attribute_value_obj, auto_detected, None

    def _auto_detect_attribute_value(self, product, file):
        """Try to match an attribute value from the uploaded filename."""
        filename_raw = os.path.splitext(file.name)[0]
        filename_lower = filename_raw.lower().replace('-', '_').replace(' ', '_')

        selected_attr_ids = product.selected_attributes.values_list('attribute_id', flat=True)
        candidate_values = AttributeValue.objects.filter(
            attribute_id__in=selected_attr_ids
        ).select_related('attribute')

        best_match = None
        best_len = 0
        for av in candidate_values:
            val_lower = av.value.lower().replace('-', '_').replace(' ', '_')
            if val_lower in filename_lower and len(val_lower) > best_len:
                best_match = av
                best_len = len(val_lower)

        return best_match

    def _generate_alt_text(self, request, product, attribute_value_obj):
        """Generate alt_text for the media, falling back to auto-generated text."""
        alt_text = request.data.get('alt_text', '')
        if alt_text:
            return alt_text

        slug = product.name.lower().replace(' ', '_')
        if attribute_value_obj:
            val_slug = attribute_value_obj.value.lower().replace(' ', '_')
            existing_count = product.media.filter(attribute_value=attribute_value_obj).count()
            return f"{slug}_{val_slug}_{existing_count + 1}"

        existing_count = product.media.filter(attribute_value__isnull=True).count()
        return f"{slug}_{existing_count + 1}" if existing_count > 0 else slug

    @extend_schema(
        summary="Delete product media",
        description="Permanently delete a media file from a product"
    )
    @action(detail=True, methods=['delete'], url_path='media/(?P<media_id>[^/.]+)/delete')
    def delete_media(self, request, pk=None, media_id=None):
        """
        Delete a specific media item from a product.
        If the deleted item was the thumbnail, auto-promote the next image.

        DELETE /api/products/{id}/media/{media_id}/delete/
        """
        product = self.get_object()
        try:
            media = product.media.get(id=media_id)
        except ProductMedia.DoesNotExist:
            return Response({'error': 'Media not found'}, status=status.HTTP_404_NOT_FOUND)

        was_thumbnail = media.is_thumbnail

        # Delete the actual file from disk
        if media.file:
            if os.path.isfile(media.file.path):
                os.remove(media.file.path)

        media.delete()

        # Auto-promote next image as thumbnail
        new_thumbnail = None
        if was_thumbnail:
            next_media = product.media.order_by('order', 'id').first()
            if next_media:
                next_media.is_thumbnail = True
                next_media.save(update_fields=['is_thumbnail'])
                new_thumbnail = next_media.id

        return Response({
            'message': 'Media deleted successfully',
            'new_thumbnail_id': new_thumbnail,
        }, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Set product thumbnail",
        description="Mark a specific media item as the product thumbnail"
    )
    @action(detail=True, methods=['post'], url_path='media/(?P<media_id>[^/.]+)/set_thumbnail')
    def set_thumbnail(self, request, pk=None, media_id=None):
        """
        Set a media item as the product thumbnail.
        POST /api/products/{id}/media/{media_id}/set_thumbnail/
        """
        product = self.get_object()
        try:
            media = product.media.get(id=media_id)
        except ProductMedia.DoesNotExist:
            return Response({'error': 'Media not found'}, status=status.HTTP_404_NOT_FOUND)

        # Clear existing thumbnails and set this one
        product.media.filter(is_thumbnail=True).update(is_thumbnail=False)
        media.is_thumbnail = True
        media.save(update_fields=['is_thumbnail'])

        return Response(ProductMediaSerializer(media, context={'request': request}).data)

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
        
        if product.product_type != ProductType.CATALOG:
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
        
        if product.product_type != ProductType.CATALOG:
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
        
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception:
            logger.exception('Unexpected error generating catalog for product %s', pk)
            return Response(
                {'error': 'Failed to generate catalog'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
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
            try:
                variant.stock = int(stock)
            except (ValueError, TypeError):
                return Response({'error': 'stock must be a number'}, status=status.HTTP_400_BAD_REQUEST)
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
            price=price,  # None = use product base price
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

    @extend_schema(
        summary="Get storefront product detail",
        description="Returns product with images grouped by attribute value (color) and variants grouped for storefront display"
    )
    @action(detail=True, methods=['get'])
    def storefront_detail(self, request, pk=None):
        """
        Storefront-friendly product detail.

        GET /api/products/{id}/storefront_detail/

        Returns product info with:
        - general_images: images not linked to any attribute value
        - attribute_groups: for each attribute (e.g. Color), each value with its images
          and available variants from other attributes (e.g. sizes)
        """
        product = self.get_object()
        serializer = StorefrontProductSerializer(product, context={'request': request})
        return Response(serializer.data)

    @extend_schema(summary="Adjust stock based on physical count")
    @action(detail=True, methods=['post'])
    def adjust_stock(self, request, pk=None):
        """
        Stock adjustment — owner enters physical count, system calculates difference.

        POST /api/products/{id}/adjust_stock/
        Body: { "physical_count": 6 }
        """
        product = self.get_object()

        physical_count = request.data.get('physical_count')
        if physical_count is None:
            return Response({'error': 'physical_count is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            physical_count = int(physical_count)
        except (ValueError, TypeError):
            return Response({'error': 'physical_count must be a number'}, status=status.HTTP_400_BAD_REQUEST)

        if physical_count < 0:
            return Response({'error': 'physical_count cannot be negative'}, status=status.HTTP_400_BAD_REQUEST)

        should_be_on_shelf = product.stock + product.reserved
        difference = physical_count - should_be_on_shelf

        if difference == 0:
            return Response({'message': 'No adjustment needed, stock matches physical count'})

        Product.objects.filter(pk=product.pk).update(
            stock=models.F('stock') + difference
        )
        product.refresh_from_db()

        return Response({
            'message': f'Stock adjusted by {"+"+str(difference) if difference > 0 else str(difference)}',
            'adjustment': difference,
            'stock': product.stock,
            'reserved': product.reserved,
            'should_be_on_shelf': product.stock + product.reserved,
        })