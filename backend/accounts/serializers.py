from typing import Any, Dict

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from companies.models import Company


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for User model representation.
    """

    company_id = serializers.IntegerField(source="company.id", read_only=True, allow_null=True)
    company_name = serializers.CharField(source="company.name", read_only=True, allow_null=True)
    full_name = serializers.CharField(source="get_full_name", read_only=True)
    is_company_admin = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "role",
            "company_id",
            "company_name",
            "is_company_admin",
            "is_active",
            "date_joined",
        ]
        read_only_fields = ["id", "role", "date_joined", "is_company_admin", "company_id", "company_name"]


class CompanyOwnerRegisterSerializer(serializers.Serializer):
    """
    Serializer for public atomic registration of a new Company and Owner user.
    Returns created user details along with JWT auth tokens for immediate login.
    """

    company_name = serializers.CharField(max_length=255, required=True)
    first_name = serializers.CharField(max_length=150, required=True)
    last_name = serializers.CharField(max_length=150, required=True)
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True, style={"input_type": "password"})
    confirm_password = serializers.CharField(write_only=True, required=True, style={"input_type": "password"})

    def validate_email(self, value: str) -> str:
        email = value.strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("A user with this email address already exists.")
        return email

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        password = attrs.get("password")
        confirm_password = attrs.get("confirm_password")

        if password != confirm_password:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})

        try:
            validate_password(password)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)})

        return attrs

    def create(self, validated_data: Dict[str, Any]) -> Dict[str, Any]:
        company_name = validated_data["company_name"].strip()
        first_name = validated_data["first_name"].strip()
        last_name = validated_data["last_name"].strip()
        email = validated_data["email"].strip().lower()
        password = validated_data["password"]

        with transaction.atomic():
            company = Company.objects.create(name=company_name)
            user = User.objects.create_user(
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                role=User.Roles.ADMIN,
                company=company,
            )

        # Generate SimpleJWT tokens
        refresh = RefreshToken.for_user(user)
        refresh["role"] = user.role
        refresh["company_id"] = company.id
        refresh["company_name"] = company.name

        return {
            "user": UserSerializer(user).data,
            "tokens": {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            },
        }


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Custom JWT Token serializer returning user and company payload upon login.
    """

    username_field = "email"

    @classmethod
    def get_token(cls, user: User):
        token = super().get_token(user)
        # Custom claims inside JWT payload
        token["email"] = user.email
        token["role"] = user.role
        token["full_name"] = user.get_full_name()
        token["is_company_admin"] = user.is_company_admin
        token["company_id"] = user.company.id if user.company else None
        token["company_name"] = user.company.name if user.company else None
        return token

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        # Authenticate with email as username
        attrs["email"] = attrs.get("email", "").strip().lower()
        inactive_user = User.objects.filter(
            email__iexact=attrs["email"],
            is_active=False,
        ).first()
        if inactive_user and inactive_user.check_password(attrs.get("password", "")):
            raise serializers.ValidationError(
                "Your account has been deactivated by admin. Contact administration."
            )

        data = super().validate(attrs)

        # Append complete serialized user profile into login response body
        data["user"] = UserSerializer(self.user).data
        return data


class UpdateProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for updating basic user profile information.
    """

    class Meta:
        model = User
        fields = ["first_name", "last_name"]


class ChangePasswordSerializer(serializers.Serializer):
    """
    Serializer for authenticated password change requests.
    """

    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True)
    confirm_new_password = serializers.CharField(required=True, write_only=True)

    def validate_old_password(self, value: str) -> str:
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Incorrect current password.")
        return value

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        new_password = attrs.get("new_password")
        confirm_new_password = attrs.get("confirm_new_password")

        if new_password != confirm_new_password:
            raise serializers.ValidationError({"confirm_new_password": "New passwords do not match."})

        try:
            validate_password(new_password, user=self.context["request"].user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"new_password": list(exc.messages)})

        return attrs

    def save(self, **kwargs: Any) -> User:
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save()
        return user
