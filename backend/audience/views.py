from django.db.models import Q
from rest_framework import generics, permissions, status

from audience.models import Audience
from audience.serializers import AudienceSerializer
from audience.services import matching_audience_records, phone_identity
from companies.permissions import IsCompanyAdmin
from utils.pagination import AdminListPagination


class AudienceListView(generics.ListCreateAPIView):
    serializer_class = AudienceSerializer
    permission_classes = [permissions.IsAuthenticated, IsCompanyAdmin]
    pagination_class = AdminListPagination

    def create(self, request, *args, **kwargs):
        self.audience_record_created = True
        response = super().create(request, *args, **kwargs)
        if (
            response.status_code == status.HTTP_201_CREATED
            and not self.audience_record_created
        ):
            response.status_code = status.HTTP_200_OK
        return response

    def get_queryset(self):
        queryset = Audience.objects.filter(company=self.request.user.company).select_related("integration")
        search = self.request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(mobile__icontains=search) | Q(email__icontains=search)
                | Q(zipcode__icontains=search) | Q(city__icontains=search) | Q(street__icontains=search)
                | Q(state__icontains=search) | Q(integration__name__icontains=search)
            )
        ordering_options = {
            "-updated_at": ("-updated_at", "-id"),
            "updated_at": ("updated_at", "id"),
            "name": ("name", "-updated_at", "-id"),
            "-name": ("-name", "-updated_at", "-id"),
        }
        ordering = self.request.query_params.get("ordering", "-updated_at")
        return queryset.order_by(*ordering_options.get(ordering, ordering_options["-updated_at"]))

    def perform_create(self, serializer):
        values = serializer.validated_data
        matches = matching_audience_records(self.request.user.company, values)
        if not matches:
            serializer.save(company=self.request.user.company)
            self.audience_record_created = True
            return

        record = matches[0]
        for attribute, value in values.items():
            if value and attribute != "integration":
                setattr(record, attribute, value)
        record.save()
        serializer.instance = record
        self.audience_record_created = False


class AudienceDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AudienceSerializer
    permission_classes = [permissions.IsAuthenticated, IsCompanyAdmin]

    def get_queryset(self):
        return Audience.objects.filter(company=self.request.user.company).select_related("integration")

    def perform_update(self, serializer):
        values = serializer.validated_data
        current = serializer.instance
        phone_changed = (
            "mobile" in values
            and phone_identity(values["mobile"]) != phone_identity(current.mobile)
        )
        email = values.get("email", current.email)
        email_unchanged = email.strip().casefold() == current.email.strip().casefold()

        if phone_changed and not email_unchanged:
            record_fields = (
                "integration",
                "name",
                "mobile",
                "email",
                "zipcode",
                "city",
                "street",
                "state",
            )
            new_values = {
                field: getattr(current, field)
                for field in record_fields
            }
            new_values.update(values)
            serializer.instance = Audience.objects.create(
                company=current.company,
                **new_values,
            )
            return

        serializer.save()
