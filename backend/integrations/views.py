from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from companies.permissions import IsCompanyAdmin
from integrations.models import Integration, IntegrationSubmission
from integrations.serializers import IntegrationSerializer, IntegrationSubmissionSerializer


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


class PublicIntegrationSubmissionView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, public_id):
        try:
            integration = Integration.objects.prefetch_related("fields").get(
                public_id=public_id,
                is_active=True,
            )
        except Integration.DoesNotExist:
            return Response({"detail": "Integration not found."}, status=status.HTTP_404_NOT_FOUND)

        data = request.data if isinstance(request.data, dict) else None
        if data is None:
            return Response({"detail": "Form data must be an object."}, status=status.HTTP_400_BAD_REQUEST)

        errors = {}
        fields_by_name = {field.name: field for field in integration.fields.all()}
        for field in integration.fields.all():
            value = data.get(field.name)
            if field.required and (value is None or value == "" or value == []):
                errors[field.name] = "This field is required."
            if field.field_type in {"select", "multi_select"} and value:
                values = value if field.field_type == "multi_select" else [value]
                invalid = [item for item in values if item not in field.options]
                if invalid:
                    errors[field.name] = "Select a valid option."

        unknown_fields = set(data) - set(fields_by_name)
        if unknown_fields:
            errors["detail"] = "The form contains an invalid field."
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        submission = IntegrationSubmission.objects.create(
            integration=integration,
            data={field.name: data.get(field.name) for field in integration.fields.all()},
        )
        return Response(
            {
                "message": "Thanks, your response has been submitted.",
                "submission_id": submission.id,
            },
            status=status.HTTP_201_CREATED,
        )