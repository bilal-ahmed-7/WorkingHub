from rest_framework import generics, permissions

from audience.models import Audience
from audience.serializers import AudienceSerializer
from companies.permissions import IsCompanyAdmin


class AudienceListCreateView(generics.ListCreateAPIView):
    serializer_class = AudienceSerializer
    permission_classes = [permissions.IsAuthenticated, IsCompanyAdmin]

    def get_queryset(self):
        return Audience.objects.filter(company=self.request.user.company)

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)


class AudienceDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AudienceSerializer
    permission_classes = [permissions.IsAuthenticated, IsCompanyAdmin]

    def get_queryset(self):
        return Audience.objects.filter(company=self.request.user.company)
