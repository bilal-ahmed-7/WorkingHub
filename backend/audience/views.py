from django.db.models import Q
from rest_framework import generics, permissions

from audience.models import Audience
from audience.serializers import AudienceSerializer
from audience.services import consolidate_audience_phone
from companies.permissions import IsCompanyAdmin
from utils.pagination import AdminListPagination


class AudienceListView(generics.ListCreateAPIView):
    serializer_class = AudienceSerializer
    permission_classes = [permissions.IsAuthenticated, IsCompanyAdmin]
    pagination_class = AdminListPagination

    def get_queryset(self):
        queryset = Audience.objects.filter(company=self.request.user.company).select_related("integration")
        search = self.request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(mobile__icontains=search) | Q(email__icontains=search)
                | Q(zipcode__icontains=search) | Q(city__icontains=search) | Q(street__icontains=search)
                | Q(state__icontains=search) | Q(integration__name__icontains=search)
            )
        return queryset

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)


class AudienceDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AudienceSerializer
    permission_classes = [permissions.IsAuthenticated, IsCompanyAdmin]

    def get_queryset(self):
        return Audience.objects.filter(company=self.request.user.company).select_related("integration")

    def perform_update(self, serializer):
        record = serializer.save()
        serializer.instance = consolidate_audience_phone(record)
