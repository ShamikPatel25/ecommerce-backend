from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import transaction
from django.db.models import Q

from products.models import Product, Category
from products.serializers import StorefrontProductSerializer, CategoryTreeSerializer
from orders.models import Order, OrderItem
from orders.serializers import OrderCreateSerializer, OrderSerializer
from orders.utils import decrement_stock
from .serializers import StorefrontStoreSerializer, StorefrontProductListSerializer


class StorefrontStoreInfoView(APIView):
    """GET /api/storefront/store/ — public store info."""
    permission_classes = [AllowAny]

    def get(self, request):
        if not request.tenant:
            return Response({'error': 'Store not found'}, status=404)
        serializer = StorefrontStoreSerializer(request.tenant)
        return Response(serializer.data)


class StorefrontCategoryListView(APIView):
    """GET /api/storefront/categories/ — active category tree."""
    permission_classes = [AllowAny]

    def get(self, request):
        if not request.tenant:
            return Response([], status=200)
        categories = Category.objects.filter(
            store=request.tenant, is_active=True, parent=None
        ).prefetch_related('children__children')
        serializer = CategoryTreeSerializer(categories, many=True)
        return Response(serializer.data)


class StorefrontProductListView(generics.ListAPIView):
    """GET /api/storefront/products/ — product listing with filters."""
    permission_classes = [AllowAny]
    serializer_class = StorefrontProductListSerializer

    def get_queryset(self):
        if not self.request.tenant:
            return Product.objects.none()

        qs = Product.objects.filter(
            store=self.request.tenant, is_active=True
        ).select_related('category').prefetch_related('media', 'variants')

        # Category filter (by slug, includes children)
        category_slug = self.request.query_params.get('category')
        if category_slug:
            try:
                cat = Category.objects.get(
                    store=self.request.tenant, slug=category_slug, is_active=True
                )
                # Include the category + all its descendants
                cat_ids = [cat.id]
                for child in cat.children.filter(is_active=True):
                    cat_ids.append(child.id)
                    for grandchild in child.children.filter(is_active=True):
                        cat_ids.append(grandchild.id)
                qs = qs.filter(category_id__in=cat_ids)
            except Category.DoesNotExist:
                pass

        # Search
        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(description__icontains=search))

        # Price range
        min_price = self.request.query_params.get('min_price')
        if min_price:
            qs = qs.filter(price__gte=min_price)
        max_price = self.request.query_params.get('max_price')
        if max_price:
            qs = qs.filter(price__lte=max_price)

        # Featured
        featured = self.request.query_params.get('featured')
        if featured == 'true':
            qs = qs.filter(is_featured=True)

        # Sort
        sort = self.request.query_params.get('sort', 'newest')
        if sort == 'price_asc':
            qs = qs.order_by('price')
        elif sort == 'price_desc':
            qs = qs.order_by('-price')
        else:
            qs = qs.order_by('-created_at')

        return qs


class StorefrontProductDetailView(APIView):
    """GET /api/storefront/products/<slug>/ — full product detail."""
    permission_classes = [AllowAny]

    def get(self, request, slug):
        if not request.tenant:
            return Response({'error': 'Store not found'}, status=404)
        try:
            product = Product.objects.select_related('category').prefetch_related(
                'media__attribute_value__attribute',
                'selected_attributes__attribute__values',
                'variants__attribute_values__attribute_value__attribute',
            ).get(store=request.tenant, slug=slug, is_active=True)
        except Product.DoesNotExist:
            return Response({'error': 'Product not found'}, status=404)

        serializer = StorefrontProductSerializer(product, context={'request': request})
        return Response(serializer.data)


class StorefrontOrderCreateView(APIView):
    """POST /api/storefront/orders/ — guest checkout order creation."""
    permission_classes = [AllowAny]

    def post(self, request):
        if not request.tenant:
            return Response({'error': 'Store not found'}, status=404)

        serializer = OrderCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        # Validate all products belong to this store
        for item_data in data['items']:
            if item_data['product'].store_id != request.tenant.id:
                return Response(
                    {'error': 'Product does not belong to this store'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        try:
            with transaction.atomic():
                order = Order.objects.create(
                    store=request.tenant,
                    customer_name=data['customer_name'],
                    customer_email=data['customer_email'],
                    customer_phone=data['customer_phone'],
                    notes=data.get('notes', ''),
                )
                for item_data in data['items']:
                    decrement_stock(item_data)
                    OrderItem.objects.create(
                        order=order,
                        product=item_data['product'],
                        variant=item_data.get('variant'),
                        quantity=item_data['quantity'],
                        unit_price=item_data['unit_price'],
                    )
                order.recalculate_total()

            return Response(
                OrderSerializer(order, context={'request': request}).data,
                status=status.HTTP_201_CREATED,
            )
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class StorefrontReturnRequestView(APIView):
    """POST /api/storefront/orders/<order_id>/return/ — customer requests return."""
    permission_classes = [AllowAny]

    def post(self, request, order_id):
        if not request.tenant:
            return Response({'error': 'Store not found'}, status=404)

        try:
            order = Order.objects.get(id=order_id, store=request.tenant)
        except Order.DoesNotExist:
            return Response({'error': 'Order not found'}, status=404)

        if order.status != 'delivered':
            return Response(
                {'error': f'Cannot request return. Order status is "{order.status}", must be "delivered".'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        order.status = 'return_requested'
        order.save(update_fields=['status', 'updated_at'])

        return Response({
            'message': 'Return request submitted successfully',
            'order_id': order.id,
            'status': order.status,
        })
