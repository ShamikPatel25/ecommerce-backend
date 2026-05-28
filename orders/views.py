import logging

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction

logger = logging.getLogger(__name__)

from datetime import timedelta
from django.utils import timezone
from django.db.models import Count, Sum, Max, F, ExpressionWrapper, DecimalField, Q

from .models import Order, OrderItem
from .serializers import (
    OrderSerializer,
    OrderCreateSerializer,
    OrderStatusUpdateSerializer,
)
from .utils import decrement_stock, restore_stock, reduce_reserved, restore_stock_only
from tenants.utils import get_tenant_model
from tenants.permissions import IsStoreOwner
from products.models import Product
from products.utils import get_product_thumbnail_url
from config.constants import (
    LOW_STOCK_THRESHOLD,
    DASHBOARD_RECENT_ORDERS_LIMIT,
    DASHBOARD_LOW_STOCK_LIMIT,
    DASHBOARD_DAYS_RANGE,
)

@extend_schema(tags=['Orders'])
@extend_schema_view(
    list=extend_schema(summary='List all orders'),
    retrieve=extend_schema(summary='Get order details'),
    destroy=extend_schema(summary='Delete an order'),
)
class OrderViewSet(viewsets.ModelViewSet):
    """Order management — list, retrieve, create, update status, delete."""
    permission_classes = [IsAuthenticated, IsStoreOwner]
    http_method_names  = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_serializer_class(self):
        if self.action == 'create':
            return OrderCreateSerializer
        if self.action == 'update_status':
            return OrderStatusUpdateSerializer
        return OrderSerializer

    def get_queryset(self):
        qs = get_tenant_model(self.request, Order).prefetch_related(
            'items__product', 'items__variant__attribute_values'
        )
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

    # ── CRUD ──────────────────────────────────────────────────────────────

    @extend_schema(summary='Create a new order', request=OrderCreateSerializer)
    def create(self, request, *args, **kwargs):
        serializer = OrderCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        # Validate all products belong to this store
        for item_data in data['items']:
            if item_data['product'].store_id != request.tenant.id:
                return Response(
                    {'error': 'Product does not belong to this store'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            with transaction.atomic():
                order = Order.objects.create(
                    store=request.tenant,
                    customer_name=data['customer_name'],
                    customer_email=data.get('customer_email'),
                    customer_phone=data.get('customer_phone'),
                    notes=data.get('notes', ''),
                    address_line_1=data.get('address_line_1', ''),
                    address_line_2=data.get('address_line_2', ''),
                    city=data.get('city', ''),
                    state=data.get('state', ''),
                    postal_code=data.get('postal_code', ''),
                    country=data.get('country', 'India'),
                    address_type=data.get('address_type', 'home'),
                )
                for item_data in data['items']:
                    # Decrement stock before creating the item
                    decrement_stock(item_data)

                    product = item_data['product']
                    variant = item_data.get('variant')

                    # Get variant attributes display if variant exists
                    variant_attrs = ''
                    if variant and hasattr(variant, 'attribute_values_display'):
                        variant_attrs = variant.attribute_values_display or ''

                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        variant=variant,
                        quantity=item_data['quantity'],
                        unit_price=item_data['unit_price'],
                        # Snapshot fields - preserve product info for order history
                        product_name_snapshot=product.name,
                        product_sku_snapshot=product.sku or '',
                        product_slug_snapshot=product.slug or '',
                        product_thumbnail_snapshot=get_product_thumbnail_url(product) or '',
                        variant_attrs_snapshot=variant_attrs,
                    )
                order.recalculate_total()

            return Response(
                OrderSerializer(order, context={'request': request}).data,
                status=status.HTTP_201_CREATED,
            )
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception('Unexpected error creating order')
            return Response({'error': 'Failed to create order'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @extend_schema(summary='Update order status', request=OrderStatusUpdateSerializer)
    @action(detail=True, methods=['patch'], url_path='status')
    def update_status(self, request, pk=None):
        serializer = OrderStatusUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        new_status = serializer.validated_data['status']

        with transaction.atomic():
            # Lock the order row to prevent concurrent status changes
            try:
                order = Order.objects.select_for_update().get(pk=pk, store=request.tenant)
            except Order.DoesNotExist:
                return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)
            old_status = order.status

            # Validate status transition
            valid_next = Order.VALID_TRANSITIONS.get(old_status, [])
            if new_status not in valid_next:
                return Response(
                    {'error': f'Cannot change status from "{old_status}" to "{new_status}". '
                              f'Allowed: {", ".join(valid_next) if valid_next else "none (final status)"}'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Cancel (before shipping) → stock +1, reserved -1
            if new_status == 'cancelled':
                restore_stock(order)

            # Shipped → reserved -1 (bottle left shelf)
            if new_status == 'shipped' and old_status != 'shipped':
                reduce_reserved(order)

            # Returned (bottle back at store) → stock +1
            if new_status == 'returned' and old_status == 'delivered':
                restore_stock_only(order)

            order.status = new_status
            if serializer.validated_data.get('notes') is not None:
                order.notes = serializer.validated_data['notes']
            order.save(update_fields=['status', 'notes', 'updated_at'])

        return Response(OrderSerializer(order, context={'request': request}).data)

    # ── Customers (aggregated from orders) ──────────────────────────────────

    @extend_schema(summary='List unique customers with order stats')
    @action(detail=False, methods=['get'], url_path='customers')
    def customers(self, request):
        from accounts.models import User

        base_qs = get_tenant_model(request, Order)
        search = request.query_params.get('search', '').strip()

        # Get order stats grouped by email
        order_stats = (
            base_qs
            .exclude(customer_email='')
            .exclude(customer_email__isnull=True)
            .values('customer_email')
            .annotate(
                total_orders=Count('id'),
                total_spent=Sum('total_amount'),
                last_order=Max('created_at'),
            )
        )

        # Build a map of email -> order stats
        stats_map = {row['customer_email'].lower(): row for row in order_stats}

        # Get profile data for these customers
        customer_emails = list(stats_map.keys())
        users = User.objects.filter(email__in=customer_emails)
        user_map = {u.email.lower(): u for u in users}

        # Build result with profile data + order stats
        result = []
        for email, stats in stats_map.items():
            user = user_map.get(email)
            if user:
                # Use profile data for name and phone
                customer_name = user.get_full_name() or email
                customer_phone = user.phone or ''
            else:
                # Fallback to order data for guest orders
                fallback = base_qs.filter(customer_email__iexact=email).order_by('-created_at').first()
                customer_name = fallback.customer_name if fallback else email
                customer_phone = fallback.customer_phone if fallback else ''

            result.append({
                'customer_name': customer_name,
                'customer_email': email,
                'customer_phone': customer_phone,
                'total_orders': stats['total_orders'],
                'total_spent': stats['total_spent'],
                'last_order': stats['last_order'],
            })

        # Apply search filter
        if search:
            search_lower = search.lower()
            result = [r for r in result if search_lower in r['customer_name'].lower() or search_lower in r['customer_email'].lower()]

        # Sort by last order
        result.sort(key=lambda x: x.get('last_order') or '', reverse=True)
        return Response(result)

    @extend_schema(summary='Orders for a single customer (by email or name)')
    @action(detail=False, methods=['get'], url_path='customers/by-email')
    def customer_detail(self, request):
        email = request.query_params.get('email', '').strip()
        name = request.query_params.get('name', '').strip()

        if not email and not name:
            return Response({'error': 'email or name query param required'}, status=400)

        base_qs = get_tenant_model(request, Order)
        if email:
            orders = base_qs.filter(customer_email=email)
        else:
            orders = base_qs.filter(customer_name__icontains=name)

        orders = orders.prefetch_related('items__product', 'items__variant__attribute_values')
        return Response(OrderSerializer(orders, many=True, context={'request': request}).data)

    # ── Dashboard Stats ─────────────────────────────────────────────────────

    @extend_schema(summary='Get dashboard statistics')
    @action(detail=False, methods=['get'], url_path='dashboard-stats')
    def dashboard_stats(self, request):
        tenant = request.tenant

        orders = get_tenant_model(request, Order)
        # Exclude cancelled and returned orders from revenue calculation
        valid_orders = orders.exclude(status__in=['cancelled', 'returned'])

        total_revenue = valid_orders.aggregate(total=Sum('total_amount'))['total'] or 0
        total_orders = orders.count()
        total_customers = orders.exclude(customer_email='').values('customer_email').distinct().count()
        pending_orders = orders.filter(status='pending').count()

        recent_orders_qs = orders.prefetch_related('items__product', 'items__variant__attribute_values').order_by('-created_at')[:DASHBOARD_RECENT_ORDERS_LIMIT]
        recent_orders = OrderSerializer(recent_orders_qs, many=True, context={'request': request}).data

        # Low stock products (simple approach)
        products_qs = Product.objects.filter(store=tenant, is_active=True).prefetch_related('variants')
        low_stock_list = []
        for p in products_qs:
            stock = sum(v.stock for v in p.variants.all()) if p.product_type == 'catalog' else p.stock
            if stock <= LOW_STOCK_THRESHOLD:
                low_stock_list.append({
                    'id': p.id,
                    'name': p.name,
                    'sku': p.sku,
                    'product_type': p.product_type,
                    'stock': stock
                })
        low_stock_list.sort(key=lambda x: x['stock'])
        low_stock_list = low_stock_list[:DASHBOARD_LOW_STOCK_LIMIT]

        today = timezone.now().date()
        revenue_by_day = []
        for i in range(DASHBOARD_DAYS_RANGE - 1, -1, -1):
            day = today - timedelta(days=i)
            day_orders = valid_orders.filter(created_at__date=day)
            revenue_by_day.append({
                'date': day.strftime('%b %d'),
                'revenue': day_orders.aggregate(total=Sum('total_amount'))['total'] or 0,
                'orders': day_orders.count()
            })

        status_counts = orders.values('status').annotate(count=Count('id'))
        status_data = [{'name': item['status'], 'value': item['count']} for item in status_counts]

        top_products_qs = OrderItem.objects.filter(
            order__store=tenant
        ).exclude(
            order__status__in=['cancelled', 'returned']
        ).values(
            'product__name', 'product__sku'
        ).annotate(
            revenue=Sum(ExpressionWrapper(F('unit_price') * F('quantity'), output_field=DecimalField()))
        ).order_by('-revenue')[:5]

        top_products = [
            {'name': item['product__name'], 'sku': item['product__sku'], 'revenue': item['revenue']}
            for item in top_products_qs
        ]

        return Response({
            'stats': {
                'orders': total_orders,
                'revenue': total_revenue,
                'pending': pending_orders,
                'customers': total_customers,
            },
            'recent_orders': recent_orders,
            'low_stock_products': low_stock_list,
            'revenue_by_day': revenue_by_day,
            'status_data': status_data,
            'top_products': top_products,
        })
