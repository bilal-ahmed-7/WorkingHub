from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404

from companies.permissions import IsCompanyAdmin
from audience.services import (
    DuplicateAudiencePhone,
    audience_values,
    phone_identity,
    sync_audience_record,
)
from integrations.models import Integration, IntegrationField, IntegrationSubmission, IntegrationSubmissionLog
from integrations.field_registry import (
    IDENTIFIER_FIELDS,
    identifier_field_for_name,
    submission_key,
)
from integrations.serializers import IntegrationSerializer, IntegrationSubmissionLogSerializer
from utils.pagination import AdminListPagination


def get_identity_key(data):
    phone = phone_identity(audience_values(data)["mobile"])
    return f"phone:{phone}" if phone else ""


def get_request_meta(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return {
        "method": request.method,
        "path": request.path,
        "content_type": request.META.get("CONTENT_TYPE", ""),
        "user_agent": request.META.get("HTTP_USER_AGENT", ""),
        "origin": request.META.get("HTTP_ORIGIN", ""),
        "referer": request.META.get("HTTP_REFERER", ""),
        "ip_address": forwarded_for.split(",")[0].strip() or request.META.get("REMOTE_ADDR", ""),
    }


def find_existing_submission(integration, identity_key):
    if not identity_key:
        return None

    candidates = list(integration.submissions.order_by("id"))
    matches = [
        submission for submission in candidates
        if submission.identity_key == identity_key or get_identity_key(submission.data) == identity_key
    ]
    if not matches:
        return None

    return matches[0]


class IntegrationListCreateView(generics.ListCreateAPIView):
    serializer_class = IntegrationSerializer
    permission_classes = [permissions.IsAuthenticated, IsCompanyAdmin]
    pagination_class = AdminListPagination

    def get_queryset(self):
        return Integration.objects.filter(company=self.request.user.company).prefetch_related("fields")

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)


class IntegrationDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = IntegrationSerializer
    permission_classes = [permissions.IsAuthenticated, IsCompanyAdmin]

    def get_queryset(self):
        return Integration.objects.filter(company=self.request.user.company).prefetch_related("fields")


class PublicIntegrationFormSerializer(IntegrationSerializer):
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["fields"] = [
            field for field in representation["fields"]
            if field.get("system_key") in {
                IntegrationField.SystemKeys.CUSTOM,
                IntegrationField.SystemKeys.EMAIL,
                IntegrationField.SystemKeys.PHONE,
                IntegrationField.SystemKeys.ADDRESS_MAIN,
            }
            and not field.get("config", {}).get("auto_filled_by")
        ]
        return representation


class PublicIntegrationFormView(generics.RetrieveAPIView):
    serializer_class = PublicIntegrationFormSerializer
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
        integration_fields = list(integration.fields.all())
        fields_by_name = {submission_key(field): field for field in integration_fields}
        has_address_field = any(
            field.system_key == IntegrationField.SystemKeys.ADDRESS_MAIN
            for field in integration_fields
        )
        supports_legacy_address_state = (
            has_address_field
            and IntegrationField.SystemKeys.ADDRESS_STATE not in {
                field.system_key for field in integration_fields
            }
        )
        matched_identifiers = set()
        for field in integration_fields:
            key = submission_key(field)
            value = data.get(key)
            identifier = next(
                (
                    definition for definition in IDENTIFIER_FIELDS
                    if definition["system_key"] == field.system_key
                ),
                None,
            ) or identifier_field_for_name(field.name)
            if identifier:
                matched_identifiers.add(identifier["system_key"])
            if (
                (field.required or identifier)
                and (value is None or value == "" or value == [])
            ):
                errors[key] = (
                    identifier["message"]
                    if identifier
                    else "This field is required."
                )
            if field.field_type in {"select", "multi_select"} and value:
                values = value if field.field_type == "multi_select" else [value]
                invalid = [item for item in values if item not in field.options]
                if invalid:
                    errors[key] = "Select a valid option."

        for identifier in IDENTIFIER_FIELDS:
            if identifier["system_key"] not in matched_identifiers:
                errors[identifier["system_key"]] = identifier["message"]

        allowed_extra_fields = {"address_state"} if supports_legacy_address_state else set()
        unknown_fields = set(data) - set(fields_by_name) - allowed_extra_fields
        if unknown_fields:
            errors["detail"] = "The form contains an invalid field."
        identity_key = get_identity_key(data)
        if errors:
            IntegrationSubmissionLog.objects.create(
                integration=integration,
                data=data,
                identity_key=identity_key,
                status=IntegrationSubmissionLog.Status.ERROR,
                error_message="Failed to save response.",
                request_meta=get_request_meta(request),
                response_status=status.HTTP_400_BAD_REQUEST,
            )
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        clean_data = {submission_key(field): data.get(submission_key(field)) for field in integration.fields.all()}
        if supports_legacy_address_state and data.get("address_state") not in (None, ""):
            clean_data["address_state"] = data["address_state"]
        try:
            sync_audience_record(integration, clean_data)
        except DuplicateAudiencePhone as exc:
            IntegrationSubmissionLog.objects.create(
                integration=integration,
                data=clean_data,
                identity_key=identity_key,
                status=IntegrationSubmissionLog.Status.ERROR,
                error_message="Failed to save response.",
                request_meta=get_request_meta(request),
                response_status=status.HTTP_400_BAD_REQUEST,
            )
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        submission = find_existing_submission(integration, identity_key)
        if submission:
            submission.data = clean_data
            submission.identity_key = identity_key
            submission.save()
        else:
            submission = IntegrationSubmission.objects.create(
                integration=integration,
                data=clean_data,
                identity_key=identity_key,
            )
        IntegrationSubmissionLog.objects.create(
            integration=integration,
            data=clean_data,
            identity_key=identity_key,
            status=IntegrationSubmissionLog.Status.SUCCESS,
            request_meta=get_request_meta(request),
            response_status=status.HTTP_201_CREATED,
        )
        return Response(
            {
                "message": "Thanks, your response has been submitted.",
                "submission_id": submission.id,
            },
            status=status.HTTP_201_CREATED,
        )


class IntegrationSubmissionLogView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsCompanyAdmin]

    def get(self, request, pk):
        integration = get_object_or_404(
            Integration,
            pk=pk,
            company=request.user.company,
        )
        logs = integration.submission_logs.all()
        paginator = AdminListPagination()
        page = paginator.paginate_queryset(logs, request, view=self)
        response = paginator.get_paginated_response(
            IntegrationSubmissionLogSerializer(page, many=True).data,
        )
        response.data.update({
            "integration": integration.name,
            "form_id": integration.id,
            "form_token": integration.public_id,
            "total_success": logs.filter(status=IntegrationSubmissionLog.Status.SUCCESS).count(),
            "total_errors": logs.filter(status=IntegrationSubmissionLog.Status.ERROR).count(),
        })
        return response
