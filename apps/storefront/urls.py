from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'customer/addresses', views.StorefrontCustomerAddressViewSet, basename='storefront-address')

urlpatterns = [
    path('', include(router.urls)),
    path('auth/register/', views.StorefrontRegisterView.as_view()),
    path('auth/login/', views.storefront_login_view),
    path('store/', views.StorefrontStoreInfoView.as_view()),
    path('categories/', views.StorefrontCategoryListView.as_view()),
    path('products/', views.StorefrontProductListView.as_view()),
    path('products/<slug:slug>/', views.StorefrontProductDetailView.as_view()),
    path('orders/', views.StorefrontOrderCreateView.as_view()),
    path('customer/orders/', views.StorefrontCustomerOrdersView.as_view()),
    path('customer/orders/<uuid:order_id>/', views.StorefrontCustomerOrderDetailView.as_view()),
    path('customer/orders/<uuid:order_id>/cancel/', views.StorefrontCustomerOrderCancelView.as_view()),
    path('customer/orders/<uuid:order_id>/return/', views.StorefrontCustomerOrderReturnView.as_view()),
    path('customer/items/<uuid:item_id>/cancel/', views.StorefrontCustomerOrderItemCancelView.as_view()),
    path('customer/items/<uuid:item_id>/return/', views.StorefrontCustomerOrderItemReturnView.as_view()),
    path('customer/profile/', views.StorefrontCustomerProfileView.as_view()),
    path('customer/password/', views.StorefrontCustomerPasswordView.as_view()),
]
