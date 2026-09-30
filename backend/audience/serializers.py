from rest_framework import serializers

from integrations.models import IntegrationSubmission


class AudienceSerializer(serializers.ModelSerializer):
    class Meta:
        model = IntegrationSubmission
        fields = [
            "id",
            "integration_name",
            "data",
            "submitted_at",
        ]
        read_only_fields = fields

    integration_name = serializers.CharField(source="integration.name", read_only=True)
