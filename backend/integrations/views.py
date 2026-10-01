from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404

from companies.permissions import IsCompanyAdmin
from integrations.models import Integration, IntegrationSubmission, IntegrationSubmissionLog
from integrations.serializers import IntegrationSerializer, IntegrationSubmissionLogSerializer
from utils.pagination import AdminListPagination


def get_identity_key(data):
    normalized_keys = [(key, key.strip().lower()) for key in data]
    candidates = [key for key, normalized in normalized_keys if "email" in normalized]
    candidates += [
        key for key, normalized in normalized_keys
        if any(token in normalized for token in ("phone", "mobile"))
    ]
    candidates += [
        key for key, normalized in normalized_keys
        if normalized in {"id", "number", "user id", "customer id"}
        or normalized.endswith(" id")
        or normalized.endswith(" number")
    ]
    for key in candidates:
        value = data.get(key)
        if value not in (None, "", []):
            normalized = ",".join(map(str, value)) if isinstance(value, list) else str(value)
            return f"{key.strip().lower()}:{normalized.strip().lower()}"
    return ""


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

    candidates = list(integration.submissions.all())
    matches = [
        submission for submission in candidates
        if submission.identity_key == identity_key or get_identity_key(submission.data) == identity_key
    ]
    if not matches:
        return None

    submission = matches[0]
    for duplicate in matches[1:]:
        duplicate.delete()
    return submission


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
        identity_key = get_identity_key(data)
        if errors:
            IntegrationSubmissionLog.objects.create(
                integration=integration,
                data=data,
                identity_key=identity_key,
                status=IntegrationSubmissionLog.Status.ERROR,
                error_message="; ".join(
                    f"{key}: {value}" for key, value in errors.items()
                ),
                request_meta=get_request_meta(request),
                response_status=status.HTTP_400_BAD_REQUEST,
            )
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        clean_data = {field.name: data.get(field.name) for field in integration.fields.all()}
        submission = find_existing_submission(integration, identity_key)
        if submission:
            submission.data = clean_data
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