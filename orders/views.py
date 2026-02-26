from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction
from django.db.models import Count, Sum, Max

from .models import Order, OrderItem
from .serializers import (
    OrderSerializer,
    OrderCreateSerializer,
    OrderStatusUpdateSerializer,
)
from tenants.utils import get_tenant_model


@extend_schema(tags=['Orders'])
@extend_schema_view(
    list=extend_schema(summary='List all orders'),
    retrieve=extend_schema(summary='Get order details'),
    destroy=extend_schema(summary='Delete an order'),
)
class OrderViewSet(viewsets.ModelViewSet):
    """Order management — list, retrieve, create, update status, delete."""
    permission_classes = [IsAuthenticated]
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

    @extend_schema(summary='Create a new order', request=OrderCreateSerializer)
    def create(self, request, *args, **kwargs):
        serializer = OrderCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        try:
            with transaction.atomic():
                order = Order.objects.create(
                    store=request.tenant,
                    customer_name=data['customer_name'],
                    customer_email=data.get('customer_email'),
                    customer_phone=data.get('customer_phone'),
                    notes=data.get('notes'),
                )
                for item_data in data['items']:
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
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(summary='Update order status', request=OrderStatusUpdateSerializer)
    @action(detail=True, methods=['patch'], url_path='status')
    def update_status(self, request, pk=None):
        order = self.get_object()
        serializer = OrderStatusUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        order.status = serializer.validated_data['status']
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

    @extend_schema(summary='Orders for a single customer (by email)')
    @action(detail=False, methods=['get'], url_path='customers/by-email')
    def customer_detail(self, request):
        email = request.query_params.get('email', '').strip()
        if not email:
            return Response({'error': 'email query param required'}, status=400)

        base_qs = get_tenant_model(request, Order)
        orders = base_qs.filter(customer_email=email).prefetch_related(
            'items__product', 'items__variant__attribute_values'
        )
        return Response(OrderSerializer(orders, many=True, context={'request': request}).data)

