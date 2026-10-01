from django.db.models import Q, CharField
from django.db.models.functions import Cast

from rest_framework import generics, permissions

from audience.serializers import AudienceSerializer
from companies.permissions import IsCompanyAdmin
from integrations.models import IntegrationSubmission
from utils.pagination import AdminListPagination


class AudienceListView(generics.ListAPIView):
    serializer_class = AudienceSerializer
    permission_classes = [permissions.IsAuthenticated, IsCompanyAdmin]
    pagination_class = AdminListPagination

    def get_queryset(self):
        queryset = IntegrationSubmission.objects.filter(
            integration__company=self.request.user.company,
        ).select_related("integration")
        search = self.request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.annotate(
                searchable_data=Cast("data", output_field=CharField()),
            ).filter(
                Q(integration__name__icontains=search)
                | Q(searchable_data__icontains=search)
            )
        return queryset
