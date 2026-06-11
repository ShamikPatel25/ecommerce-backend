from drf_spectacular.utils import extend_schema
import logging
from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str

from .serializers import (
    UserRegistrationSerializer, UserSerializer, UserProfileUpdateSerializer,
    ChangePasswordSerializer, ForgotPasswordSerializer, ResetPasswordSerializer,
    CustomerAddressSerializer,
)
from .models import CustomerAddress

User = get_user_model()
logger = logging.getLogger(__name__)


def _generate_tokens(user, request):
    """Generate JWT tokens with lifetime based on whether request is from storefront or admin."""
    refresh = RefreshToken.for_user(user)
    if request.headers.get('X-Tenant'):
        refresh.set_exp(lifetime=settings.STOREFRONT_REFRESH_TOKEN_LIFETIME)
        # access_token is a property that creates a new instance each time,
        # so we must capture it, set_exp, and return it separately.
        access = refresh.access_token
        access.set_exp(lifetime=settings.STOREFRONT_ACCESS_TOKEN_LIFETIME)
        return refresh, str(access)
    return refresh, str(refresh.access_token)

@extend_schema(tags=['Authentication'])
class RegisterView(generics.CreateAPIView):
    """
    Register a new user account

    Creates a new user and returns JWT tokens for immediate authentication.
    """
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = UserRegistrationSerializer
    
    @extend_schema(
        summary="Register new user",
        description="Create a new user account with email and password. Returns user data and JWT tokens.",
        responses={
            201: {
                'type': 'object',
                'properties': {
                    'user': {'type': 'object'},
                    'tokens': {
                        'type': 'object',
                        'properties': {
                            'access': {'type': 'string'},
                            'refresh': {'type': 'string'},
                        }
                    },
                    'message': {'type': 'string'}
                }
            }
        }
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Generate JWT tokens
        refresh, access_token = _generate_tokens(user, request)

        return Response({
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': access_token,
            },
            'message': 'User registered successfully'
        }, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=['Authentication'],
    summary="Login user",
    description="Authenticate user with email and password. Returns JWT tokens.",
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'email': {'type': 'string', 'format': 'email'},
                'password': {'type': 'string', 'format': 'password'},
            },
            'required': ['email', 'password']
        }
    },
    responses={
        200: {
            'type': 'object',
            'properties': {
                'user': {'type': 'object'},
                'tokens': {
                    'type': 'object',
                    'properties': {
                        'access': {'type': 'string'},
                        'refresh': {'type': 'string'},
                    }
                },
                'message': {'type': 'string'}
            }
        },
        401: {'description': 'Invalid credentials'}
    }
)
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def login_view(request):
    """User login endpoint"""
    email = request.data.get('email')
    password = request.data.get('password')
    
    if not email or not password:
        return Response({
            'error': 'Please provide both email and password'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Authenticate user
    user = authenticate(request, username=email, password=password)
    
    if user is None:
        return Response({
            'error': 'Invalid credentials'
        }, status=status.HTTP_401_UNAUTHORIZED)
    
    # Generate tokens
    refresh, access_token = _generate_tokens(user, request)

    return Response({
        'user': UserSerializer(user).data,
        'tokens': {
            'refresh': str(refresh),
            'access': access_token,
        },
        'message': 'Login successful'
    })


@extend_schema(
    tags=['Authentication'],
    summary="Get current user profile",
    description="Returns the authenticated user's profile information",
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_profile_view(request):
    """Get current user profile"""
    serializer = UserSerializer(request.user)
    return Response(serializer.data)


@extend_schema(
    tags=['Authentication'],
    summary="Update user profile",
    description="Update the authenticated user's profile (first_name, last_name, phone, username)",
    request=UserProfileUpdateSerializer,
)
@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_profile_view(request):
    """Update current user profile"""
    serializer = UserProfileUpdateSerializer(
        request.user, data=request.data, partial=True, context={'request': request}
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(UserSerializer(request.user).data)


@extend_schema(
    tags=['Authentication'],
    summary="Change password",
    description="Change the authenticated user's password",
    request=ChangePasswordSerializer,
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password_view(request):
    """Change current user password"""
    serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
    serializer.is_valid(raise_exception=True)
    request.user.set_password(serializer.validated_data['new_password'])
    request.user.save()
    return Response({'message': 'Password changed successfully'})


@extend_schema(
    tags=['Authentication'],
    summary="Request password reset",
    description="Send a password reset link to the user's email. Always returns success message for security.",
    request=ForgotPasswordSerializer,
)
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def forgot_password_view(request):
    serializer = ForgotPasswordSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    email = serializer.validated_data['email'].lower()

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response({'message': "If an account with that email exists, we've sent a password reset link."})



    # Generate token and build reset URL
    token = default_token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))

    reset_url = f"/reset-password?uid={uid}&token={token}"

    logger.info('Password reset requested for %s — link: %s', email, reset_url)

    # Bypass email and return the reset_url directly for valid owners
    return Response({
        'redirect_url': reset_url,
        'message': 'Valid owner email. Redirecting...'
    })


@extend_schema(
    tags=['Authentication'],
    summary="Verify reset token",
    description="Check if a password reset token is still valid.",
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'uid': {'type': 'string'},
                'token': {'type': 'string'}
            },
            'required': ['uid', 'token']
        }
    },
)
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def verify_reset_token_view(request):
    uid = request.data.get('uid')
    token = request.data.get('token')

    if not uid or not token:
        return Response({'valid': False, 'error': 'Missing uid or token'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user_id = force_str(urlsafe_base64_decode(uid))
        user = User.objects.get(pk=user_id)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        return Response({'valid': False, 'error': 'Invalid link'})

    if default_token_generator.check_token(user, token):
        return Response({'valid': True})
    else:
        return Response({'valid': False, 'error': 'Link has expired or is invalid'})


@extend_schema(
    tags=['Authentication'],
    summary="Reset password",
    description="Set a new password using the reset token.",
    request=ResetPasswordSerializer,
)
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def reset_password_view(request):
    serializer = ResetPasswordSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    uid = serializer.validated_data['uid']
    token = serializer.validated_data['token']

    try:
        user_id = force_str(urlsafe_base64_decode(uid))
        user = User.objects.get(pk=user_id)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        return Response({'error': 'Invalid reset link'}, status=status.HTTP_400_BAD_REQUEST)

    if not default_token_generator.check_token(user, token):
        return Response({'error': 'Reset link has expired. Please request a new one.'}, status=status.HTTP_400_BAD_REQUEST)

    user.set_password(serializer.validated_data['new_password'])
    user.save()
    return Response({'message': 'Password has been reset successfully. You can now sign in.'})


@extend_schema(tags=['Addresses'], summary="List or create addresses")
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def address_list_create_view(request):
    if request.method == 'GET':
        addresses = CustomerAddress.objects.filter(user=request.user)
        return Response(CustomerAddressSerializer(addresses, many=True).data)

    serializer = CustomerAddressSerializer(data=request.data, context={'request': request})
    serializer.is_valid(raise_exception=True)
    serializer.save(user=request.user)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@extend_schema(tags=['Addresses'], summary="Update or delete an address")
@api_view(['PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def address_detail_view(request, pk):
    try:
        address = CustomerAddress.objects.get(pk=pk, user=request.user)
    except CustomerAddress.DoesNotExist:
        return Response({'error': 'Address not found'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'DELETE':
        address.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    serializer = CustomerAddressSerializer(address, data=request.data, partial=True, context={'request': request})
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)