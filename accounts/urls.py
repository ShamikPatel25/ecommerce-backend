from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

urlpatterns = [
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.login_view, name='login'),

    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    path('profile/', views.user_profile_view, name='user-profile'),
    path('profile/update/', views.update_profile_view, name='user-profile-update'),
    path('profile/change-password/', views.change_password_view, name='change-password'),

    path('forgot-password/', views.forgot_password_view, name='forgot-password'),
    path('verify-reset-token/', views.verify_reset_token_view, name='verify-reset-token'),
    path('reset-password/', views.reset_password_view, name='reset-password'),
]