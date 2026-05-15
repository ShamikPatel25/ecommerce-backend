from django.urls import path
from . import views

urlpatterns = [
    path('store/', views.StorefrontStoreInfoView.as_view()),
    path('categories/', views.StorefrontCategoryListView.as_view()),
    path('products/', views.StorefrontProductListView.as_view()),
    path('products/<slug:slug>/', views.StorefrontProductDetailView.as_view()),
    path('orders/', views.StorefrontOrderCreateView.as_view()),
    path('customer/orders/', views.StorefrontCustomerOrdersView.as_view()),
    path('customer/orders/<int:order_id>/', views.StorefrontCustomerOrderDetailView.as_view()),
    path('customer/orders/<int:order_id>/cancel/', views.StorefrontCustomerOrderCancelView.as_view()),
    path('customer/orders/<int:order_id>/return/', views.StorefrontCustomerOrderReturnView.as_view()),
    path('customer/items/<int:item_id>/cancel/', views.StorefrontCustomerOrderItemCancelView.as_view()),
    path('customer/items/<int:item_id>/return/', views.StorefrontCustomerOrderItemReturnView.as_view()),
]
