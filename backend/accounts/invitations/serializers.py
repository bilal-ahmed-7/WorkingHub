from typing import Any, Dict

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from accounts.serializers import UserSerializer
from companies.models import Company
from accounts.invitations.models import Invitation


class InvitationSerializer(serializers.ModelSerializer):
    """
    Serializer for Invitation representation.
    """

    company_id = serializers.IntegerField(source="company.id", read_only=True)
    company_name = serializers.CharField(source="company.name", read_only=True)
    is_valid = serializers.SerializerMethodField()

    class Meta:
        model = Invitation
        fields = [
            "id",
            "email",
            "token",
            "company_id",
            "company_name",
            "is_accepted",
            "is_valid",
            "created_at",
            "expires_at",
        ]
        read_only_fields = fields

    def get_is_valid(self, obj: Invitation) -> bool:
        return obj.is_valid()


class SendInvitationSerializer(serializers.Serializer):
    """
    Serializer for company owners dispatching invitations to workers.
    """

    email = serializers.EmailField(required=True)

    def validate_email(self, value: str) -> str:
        email = value.strip().lower()
        request = self.context.get("request")
        company: Company = request.user.company

        # Check if user is already an active member with permanent credentials
        existing_user = User.objects.filter(email__iexact=email).first()
        has_pending_invite = Invitation.objects.filter(
            company=company,
            email__iexact=email,
            is_accepted=False,
        ).exists()

        if existing_user and existing_user.company == company and not has_pending_invite:
            if existing_user.first_name:
                raise serializers.ValidationError("This user is already an active verified member of your company.")

        return email


class AcceptInvitationSerializer(serializers.Serializer):
    """
    Serializer for invited workers to set their profile details and permanent password.
    No temporary password is required; the token itself securely validates identity.
    Returns the user profile and fresh SimpleJWT tokens.
    """

    token = serializers.CharField(required=True)
    first_name = serializers.CharField(max_length=150, required=True)
    last_name = serializers.CharField(max_length=150, required=True)
    new_password = serializers.CharField(required=True, write_only=True)
    confirm_new_password = serializers.CharField(required=True, write_only=True)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        token = attrs.get("token")
        new_password = attrs.get("new_password")
        confirm_new_password = attrs.get("confirm_new_password")

        # 1. Validate Invitation Token
        invitation = Invitation.objects.select_related("company").filter(token=token).first()
        if not invitation:
            raise serializers.ValidationError({"token": "Invalid invitation token."})

        if invitation.is_accepted:
            raise serializers.ValidationError({"token": "This invitation has already been accepted."})

        if timezone.now() > invitation.expires_at:
            raise serializers.ValidationError({"token": "This invitation has expired."})

        # 2. Password matching and complexity validation
        if new_password != confirm_new_password:
            raise serializers.ValidationError({"confirm_new_password": "Passwords do not match."})

        try:
            validate_password(new_password)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"new_password": list(exc.messages)})

        attrs["invitation"] = invitation
        return attrs

    def save(self, **kwargs: Any) -> Dict[str, Any]:
        invitation: Invitation = self.validated_data["invitation"]
        first_name: str = self.validated_data["first_name"].strip()
        last_name: str = self.validated_data["last_name"].strip()
        new_password: str = self.validated_data["new_password"]

        with transaction.atomic():
            user = User.objects.filter(email__iexact=invitation.email).first()
            if user is None:
                user = User.objects.create_user(
                    email=invitation.email,
                    password=new_password,
                    first_name=first_name,
                    last_name=last_name,
                    role=User.Roles.WORKER,
                    company=invitation.company,
                )
            else:
                user.first_name = first_name
                user.last_name = last_name
                user.role = User.Roles.WORKER
                user.company = invitation.company
                user.set_password(new_password)
                user.save()

            invitation.is_accepted = True
            invitation.save(update_fields=["is_accepted"])

        # Generate JWT tokens for immediate auto-login
        refresh = RefreshToken.for_user(user)
        refresh["role"] = user.role
        refresh["company_id"] = user.company.id if user.company else None
        refresh["company_name"] = user.company.name if user.company else None

        return {
            "user": UserSerializer(user).data,
            "tokens": {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            },
        }
