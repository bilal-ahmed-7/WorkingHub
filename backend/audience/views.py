from rest_framework import generics, permissions

from audience.serializers import AudienceSerializer
from companies.permissions import IsCompanyAdmin
from integrations.models import IntegrationSubmission


class AudienceListView(generics.ListAPIView):
    serializer_class = AudienceSerializer
    permission_classes = [permissions.IsAuthenticated, IsCompanyAdmin]

    def get_queryset(self):
        return IntegrationSubmission.objects.filter(
            integration__company=self.request.user.company,
        ).select_related("integration")
