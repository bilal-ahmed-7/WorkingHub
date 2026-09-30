import logging

from django.conf import settings
from django.core.mail import send_mail
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from accounts.serializers import (
    ChangePasswordSerializer,
    CompanyOwnerRegisterSerializer,
    CustomTokenObtainPairSerializer,
    UpdateProfileSerializer,
    UserSerializer,
)

logger = logging.getLogger(__name__)


class RegisterOwnerView(APIView):
    """
    Public registration endpoint for Company Owners.
    Creates a new Company and Owner User atomically, returning user data and JWT tokens.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = CompanyOwnerRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        owner = result["user"]
        frontend_url = settings.FRONTEND_URL.rstrip("/")
        try:
            send_mail(
                subject="Welcome to WorkHub",
                message=(
                    f"Hello {owner['first_name']},\n\n"
                    f"Welcome to WorkHub. Your workspace for {owner['company_name']} is ready.\n\n"
                    f"Sign in at {frontend_url}/login\n\n"
                    "The WorkHub Team"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[owner["email"]],
                fail_silently=False,
            )
        except Exception:
            logger.exception("Unable to send owner welcome email to %s", owner["email"])

        return Response(
            {
                "message": "Company and Owner account registered successfully.",
                "user": result["user"],
                "tokens": result["tokens"],
            },
            status=status.HTTP_201_CREATED,
        )


class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Email-based JWT authentication view returning access & refresh tokens plus user profile.
    """

    serializer_class = CustomTokenObtainPairSerializer
    permission_classes = [permissions.AllowAny]


class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    Endpoint for retrieving and updating the authenticated user's profile.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method in ["PUT", "PATCH"]:
            return UpdateProfileSerializer
        return UserSerializer

    def get_object(self) -> User:
        return self.request.user


class ChangePasswordView(APIView):
    """
    Endpoint for authenticated users to update their password.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"message": "Password updated successfully."},
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    """
    Logout endpoint. If blacklist is enabled, blacklists the given refresh token.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        refresh_token = request.data.get("refresh")
        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
            except Exception:
                # If token is invalid or blacklist not active, proceed gracefully
                pass
        return Response(
            {"message": "Logged out successfully."},
            status=status.HTTP_200_OK,
        )
