from functools import wraps

from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import transaction
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce

from products.models import Product, Category
from products.serializers import StorefrontProductSerializer, CategoryTreeSerializer
from orders.models import Order, OrderItem
from orders.serializers import OrderCreateSerializer, OrderSerializer
from orders.utils import decrement_stock
from storefront.authentication import OptionalJWTAuthentication
from .serializers import StorefrontStoreSerializer, StorefrontProductListSerializer

_STORE_NOT_FOUND = Response({'error': 'Store not found'}, status=404)


def require_tenant(fn):
    """Decorator that returns 404 when request.tenant is falsy."""
    @wraps(fn)
    def wrapper(self_or_request, *args, **kwargs):
        # Works for both APIView methods (self, request, ...) and function views (request, ...)
        request = args[0] if args and hasattr(args[0], 'tenant') else self_or_request
        if not request.tenant:
            return Response({'error': 'Store not found'}, status=404)
        return fn(self_or_request, *args, **kwargs)
    return wrapper


class StorefrontStoreInfoView(APIView):
    """GET /api/storefront/store/ — public store info."""
    permission_classes = [AllowAny]
    authentication_classes = []

    @require_tenant
    def get(self, request):
        serializer = StorefrontStoreSerializer(request.tenant)
        return Response(serializer.data)


class StorefrontCategoryListView(APIView):
    """GET /api/storefront/categories/ — active category tree."""
    permission_classes = [AllowAny]
    authentication_classes = []

    @require_tenant
    def get(self, request):
        categories = Category.objects.filter(
            store=request.tenant, is_active=True, parent=None
        ).prefetch_related('children__children')
        serializer = CategoryTreeSerializer(categories, many=True)
        return Response(serializer.data)


def _annotate_variant_stock(qs):
    """Annotate a Product queryset with _variant_stock (total active-variant stock)."""
    return qs.annotate(
        _variant_stock=Coalesce(
            Sum('variants__stock', filter=Q(variants__is_active=True)),
            0
        )
    )


class StorefrontProductListView(generics.ListAPIView):
    """GET /api/storefront/products/ — product listing with filters."""
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = StorefrontProductListSerializer

    def get_queryset(self):
        if not self.request.tenant:
            return Product.objects.none()

        qs = Product.objects.filter(
            store=self.request.tenant, is_active=True
        ).select_related('category').prefetch_related('media', 'variants')

        # Hide out-of-stock products
        qs = _annotate_variant_stock(qs).exclude(
            product_type='single', stock=0
        ).exclude(
            product_type='catalog', _variant_stock=0
        )

        # Category filter (by slug, includes children)
        category_slug = self.request.query_params.get('category')
        if category_slug:
            qs = self._filter_by_category(qs, category_slug)
            if qs is None:
                return Product.objects.none()

        # Search
        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(description__icontains=search))

        # Price range
        min_price = self.request.query_params.get('min_price')
        if min_price:
            try:
                qs = qs.filter(price__gte=float(min_price))
            except ValueError:
                pass
        max_price = self.request.query_params.get('max_price')
        if max_price:
            try:
                qs = qs.filter(price__lte=float(max_price))
            except ValueError:
                pass

        # Featured
        featured = self.request.query_params.get('featured')
        if featured == 'true':
            qs = qs.filter(is_featured=True)

        return self._apply_sort(qs)

    def _filter_by_category(self, qs, category_slug):
        """Filter queryset by category slug, including child categories.

        Returns the filtered queryset, or None if the category does not exist.
        """
        try:
            cat = Category.objects.get(
                store=self.request.tenant, slug=category_slug, is_active=True
            )
        except Category.DoesNotExist:
            return None

        cat_ids = [cat.id]
        for child in cat.children.filter(is_active=True):
            cat_ids.append(child.id)
            for grandchild in child.children.filter(is_active=True):
                cat_ids.append(grandchild.id)
        return qs.filter(category_id__in=cat_ids)

    def _apply_sort(self, qs):
        """Apply sorting to the queryset based on the 'sort' query param."""
        sort = self.request.query_params.get('sort', 'newest')
        if sort == 'price_asc':
            return qs.order_by('price')
        if sort == 'price_desc':
            return qs.order_by('-price')
        return qs.order_by('-created_at')


class StorefrontProductDetailView(APIView):
    """GET /api/storefront/products/<slug>/ — full product detail."""
    permission_classes = [AllowAny]
    authentication_classes = []

    @require_tenant
    def get(self, request, slug):
        try:
            product = _annotate_variant_stock(
                Product.objects.select_related('category').prefetch_related(
                    'media__attribute_value__attribute',
                    'selected_attributes__attribute__values',
                    'variants__attribute_values__attribute_value__attribute',
                )
            ).get(store=request.tenant, slug=slug, is_active=True)
        except Product.DoesNotExist:
            return Response({'error': 'Product not found'}, status=404)

        # Hide out-of-stock products
        is_out_of_stock = (
            (product.product_type == 'single' and product.stock == 0)
            or (product.product_type == 'catalog' and product._variant_stock == 0)
        )
        if is_out_of_stock:
            return Response({'error': 'Product not found'}, status=404)

        serializer = StorefrontProductSerializer(product, context={'request': request})
        return Response(serializer.data)


class StorefrontOrderCreateView(APIView):
    """POST /api/storefront/orders/ — guest checkout order creation."""
    permission_classes = [AllowAny]
    authentication_classes = [OptionalJWTAuthentication]

    @require_tenant
    def post(self, request):
        serializer = OrderCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        # If authenticated, use the user's info
        if request.user.is_authenticated:
            data['customer_email'] = request.user.email
            if request.user.get_full_name().strip():
                data['customer_name'] = request.user.get_full_name()

        # Validate all products belong to this store and enforce server-side pricing
        for item_data in data['items']:
            product = item_data['product']
            variant = item_data.get('variant')
            if product.store_id != request.tenant.id:
                return Response(
                    {'error': 'Product does not belong to this store'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            # Enforce the real price — never trust client-submitted unit_price
            if variant and variant.price is not None:
                item_data['unit_price'] = variant.price
            else:
                item_data['unit_price'] = product.price

        try:
            with transaction.atomic():
                order = Order.objects.create(
                    store=request.tenant,
                    customer_name=data['customer_name'],
                    customer_email=data['customer_email'],
                    customer_phone=data['customer_phone'],
                    notes=data.get('notes', ''),
                    address_line_1=data['address_line_1'],
                    address_line_2=data.get('address_line_2', ''),
                    city=data['city'],
                    state=data['state'],
                    postal_code=data['postal_code'],
                    country=data.get('country', 'India'),
                    address_type=data.get('address_type', 'home'),
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
    permission_classes = [IsAuthenticated]

    @require_tenant
    def post(self, request, order_id):
        try:
            order = Order.objects.get(
                id=order_id,
                store=request.tenant,
                customer_email__iexact=request.user.email,
            )
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


class StorefrontCustomerOrdersView(APIView):
    """GET /api/storefront/customer/orders/ — list orders for logged-in customer."""
    permission_classes = [IsAuthenticated]

    @require_tenant
    def get(self, request):
        orders = Order.objects.filter(
            store=request.tenant,
            customer_email__iexact=request.user.email
        ).prefetch_related(
            'items__product__media',
            'items__variant__attribute_values',
        ).order_by('-created_at')
        serializer = OrderSerializer(orders, many=True, context={'request': request})
        return Response(serializer.data)


class StorefrontCustomerOrderDetailView(APIView):
    """GET /api/storefront/customer/orders/<id>/ — order detail for logged-in customer."""
    permission_classes = [IsAuthenticated]

    @require_tenant
    def get(self, request, order_id):
        try:
            order = Order.objects.prefetch_related('items__product').get(
                id=order_id, store=request.tenant, customer_email__iexact=request.user.email
            )
        except Order.DoesNotExist:
            return Response({'error': 'Order not found'}, status=404)
        serializer = OrderSerializer(order, context={'request': request})
        return Response(serializer.data)
