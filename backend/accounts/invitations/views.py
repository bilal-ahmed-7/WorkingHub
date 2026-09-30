from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from companies.permissions import IsCompanyAdmin
from accounts.invitations.models import Invitation
from accounts.invitations.serializers import (
    AcceptInvitationSerializer,
    InvitationSerializer,
    SendInvitationSerializer,
)
from accounts.invitations.services import dispatch_worker_invitation


class SendInvitationView(APIView):
    """
    Endpoint for Company Owners to invite prospective workers via email.
    """

    permission_classes = [permissions.IsAuthenticated, IsCompanyAdmin]

    def post(self, request, *args, **kwargs):
        serializer = SendInvitationSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        frontend_base_url = request.data.get("frontend_url", "")

        invitation, email_sent, message = dispatch_worker_invitation(
            inviter=request.user,
            email=email,
            frontend_base_url=frontend_base_url,
        )

        return Response(
            {
                "message": message,
                "email_sent": email_sent,
                "invitation": InvitationSerializer(invitation).data,
            },
            status=status.HTTP_201_CREATED,
        )


class ValidateInvitationView(APIView):
    """
    Public endpoint for frontend to check validity of an invitation token before rendering the form.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request, token: str, *args, **kwargs):
        invitation = Invitation.objects.select_related("company").filter(token=token).first()

        if not invitation:
            return Response(
                {"valid": False, "error": "Invitation not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if invitation.is_accepted:
            return Response(
                {"valid": False, "error": "Invitation has already been accepted."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not invitation.is_valid():
            return Response(
                {"valid": False, "error": "Invitation token has expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "valid": True,
                "email": invitation.email,
                "company_name": invitation.company.name,
                "expires_at": invitation.expires_at,
            },
            status=status.HTTP_200_OK,
        )


class AcceptInvitationView(APIView):
    """
    Public endpoint for invited workers to submit profile details and choose their permanent password.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = AcceptInvitationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = serializer.save()

        return Response(
            {
                "message": "Invitation accepted successfully! Your permanent password is set.",
                "user": result["user"],
                "tokens": result["tokens"],
            },
            status=status.HTTP_200_OK,
        )


class InvitationListView(generics.ListAPIView):
    """
    Endpoint for listing all invitations within the owner's company tenant.
    """

    serializer_class = InvitationSerializer
    permission_classes = [permissions.IsAuthenticated, IsCompanyAdmin]

    def get_queryset(self):
        return Invitation.objects.filter(
            company=self.request.user.company,
            is_accepted=False,
            expires_at__gt=timezone.now(),
        ).order_by("-created_at")


class RevokeInvitationView(generics.DestroyAPIView):
    """
    Endpoint for company owners to revoke/delete an invitation.
    """

    permission_classes = [permissions.IsAuthenticated, IsCompanyAdmin]
    lookup_field = "token"

    def get_queryset(self):
        return Invitation.objects.filter(
            company=self.request.user.company,
        )
