from rest_framework import generics, permissions

from companies.permissions import IsCompanyAdmin
from integrations.models import Integration
from integrations.serializers import IntegrationSerializer


class IntegrationListCreateView(generics.ListCreateAPIView):
    serializer_class = IntegrationSerializer
    permission_classes = [permissions.IsAuthenticated, IsCompanyAdmin]

    def get_queryset(self):
        return Integration.objects.filter(company=self.request.user.company).prefetch_related("fields")

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)


class IntegrationDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = IntegrationSerializer
    permission_classes = [permissions.IsAuthenticated, IsCompanyAdmin]

    def get_queryset(self):
        return Integration.objects.filter(company=self.request.user.company).prefetch_related("fields")


class PublicIntegrationFormView(generics.RetrieveAPIView):
    serializer_class = IntegrationSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = "public_id"
    lookup_url_kwarg = "public_id"
    queryset = Integration.objects.filter(is_active=True).prefetch_related("fields")