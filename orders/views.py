import logging

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction
from django.db.models import Count, Sum, Max

logger = logging.getLogger(__name__)

from datetime import timedelta
from django.utils import timezone
from django.db.models import Count, Sum, Max, F, ExpressionWrapper, DecimalField

from .models import Order, OrderItem
from .serializers import (
    OrderSerializer,
    OrderCreateSerializer,
    OrderStatusUpdateSerializer,
)
from .utils import decrement_stock, restore_stock, reduce_reserved, restore_stock_only
from tenants.utils import get_tenant_model
from tenants.permissions import IsStoreOwner
from products.models import Product, Category

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
        base_qs = get_tenant_model(request, Order)
        search = request.query_params.get('search', '').strip()
        if search:
            base_qs = base_qs.filter(customer_name__icontains=search)

        rows = (
            base_qs
            .values('customer_name', 'customer_email', 'customer_phone')
            .annotate(
                total_orders=Count('id'),
                total_spent=Sum('total_amount'),
                last_order=Max('created_at'),
            )
            .order_by('-last_order')
        )
        return Response(list(rows))

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
        total_products = Product.objects.filter(store=tenant).count()
        total_categories = Category.objects.filter(store=tenant).count()
        total_customers = orders.exclude(customer_email='').values('customer_email').distinct().count()
        pending_orders = orders.filter(status='pending').count()

        recent_orders_qs = orders.prefetch_related('items__product', 'items__variant__attribute_values').order_by('-created_at')[:5]
        recent_orders = OrderSerializer(recent_orders_qs, many=True, context={'request': request}).data

        # Low stock products (simple approach)
        products_qs = Product.objects.filter(store=tenant, is_active=True).prefetch_related('variants')
        low_stock_list = []
        for p in products_qs:
            stock = sum(v.stock for v in p.variants.all()) if p.product_type == 'catalog' else p.stock
            if stock <= 10:
                low_stock_list.append({
                    'id': p.id,
                    'name': p.name,
                    'sku': p.sku,
                    'product_type': p.product_type,
                    'stock': stock
                })
        low_stock_list.sort(key=lambda x: x['stock'])
        low_stock_list = low_stock_list[:5]

        today = timezone.now().date()
        revenue_by_day = []
        for i in range(6, -1, -1):
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
                'products': total_products,
                'categories': total_categories,
                'pending': pending_orders,
                'customers': total_customers,
            },
            'recent_orders': recent_orders,
            'low_stock_products': low_stock_list,
            'revenue_by_day': revenue_by_day,
            'status_data': status_data,
            'top_products': top_products,
        })
