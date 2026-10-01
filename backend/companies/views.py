from django.db.models import Q
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from companies.models import Company
from companies.permissions import IsCompanyAdmin, IsCompanyMember
from companies.serializers import CompanySerializer, WorkerSerializer, WorkerStatusSerializer
from utils.pagination import AdminListPagination


class CompanyDetailView(generics.RetrieveUpdateAPIView):
    """
    Endpoint for retrieving and updating the authenticated user's company information.
    Updating requires Company Owner (ADMIN) privileges.
    """

    serializer_class = CompanySerializer

    def get_permissions(self):
        if self.request.method in ["PUT", "PATCH"]:
            return [permissions.IsAuthenticated(), IsCompanyAdmin()]
        return [permissions.IsAuthenticated(), IsCompanyMember()]

    def get_object(self) -> Company:
        return self.request.user.company


class CompanyStatsView(APIView):
    """
    Role-Aware Dashboard Analytics endpoint.
    Returns organization metrics for Owners, or workspace overview for Workers.
    """

    permission_classes = [permissions.IsAuthenticated, IsCompanyMember]

    def get(self, request, *args, **kwargs):
        user = request.user
        company = user.company
        now = timezone.now()

        # Import lazily to avoid circular dependency
        from accounts.invitations.models import Invitation
        from accounts.invitations.serializers import InvitationSerializer

        if user.is_company_admin:
            workers_qs = User.objects.filter(
                company=company,
                role=User.Roles.WORKER,
            ).exclude(password__startswith="!")
            pending_invites_qs = Invitation.objects.filter(
                company=company,
                is_accepted=False,
                expires_at__gt=now,
            )

            total_workers = workers_qs.count()
            active_users = User.objects.filter(
                company=company,
                is_active=True,
            ).exclude(role=User.Roles.WORKER, password__startswith="!").count()
            pending_invites_count = pending_invites_qs.count()

            recent_workers = workers_qs.order_by("-date_joined")[:5]
            recent_invitations = pending_invites_qs.order_by("-created_at")[:5]

            data = {
                "is_admin": True,
                "company": CompanySerializer(company).data,
                "metrics": {
                    "total_workers": total_workers,
                    "active_users": active_users,
                    "pending_invites": pending_invites_count,
                },
                "recent_workers": WorkerSerializer(recent_workers, many=True).data,
                "recent_invitations": InvitationSerializer(recent_invitations, many=True).data,
            }
        else:
            colleagues_count = User.objects.filter(
                company=company,
                is_active=True,
            ).exclude(role=User.Roles.WORKER, password__startswith="!").count()
            data = {
                "is_admin": False,
                "company": CompanySerializer(company).data,
                "metrics": {
                    "colleagues_count": colleagues_count,
                },
            }

        return Response(data, status=status.HTTP_200_OK)


class CompanyWorkersListView(generics.ListAPIView):
    """
    Endpoint for listing all workers belonging to the authenticated user's company.
    """

    serializer_class = WorkerSerializer
    permission_classes = [permissions.IsAuthenticated, IsCompanyMember]
    pagination_class = AdminListPagination

    def get_queryset(self):
        queryset = User.objects.filter(
            company=self.request.user.company,
            role=User.Roles.WORKER,
        ).exclude(password__startswith="!").order_by("-date_joined")
        search = self.request.query_params.get("search", "").strip()
        if search:
            name_parts = search.split()
            queryset = queryset.filter(
                Q(email__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | (Q(first_name__icontains=name_parts[0]) & Q(last_name__icontains=name_parts[-1]))
            )
        return queryset


class CompanyWorkerDeleteView(generics.DestroyAPIView):
    """
    Endpoint for company owners to remove a worker from their company tenant.
    """

    permission_classes = [permissions.IsAuthenticated, IsCompanyAdmin]

    def get_queryset(self):
        return User.objects.filter(
            company=self.request.user.company,
            role=User.Roles.WORKER,
        )

    def perform_destroy(self, instance: User):
        instance.delete()


class CompanyWorkerStatusView(generics.UpdateAPIView):
    """Allow company owners to activate or deactivate an accepted worker."""

    serializer_class = WorkerStatusSerializer
    permission_classes = [permissions.IsAuthenticated, IsCompanyAdmin]
    http_method_names = ["patch", "options"]

    def get_queryset(self):
        return User.objects.filter(
            company=self.request.user.company,
            role=User.Roles.WORKER,
        ).exclude(password__startswith="!")
