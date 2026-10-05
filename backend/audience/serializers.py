from rest_framework import serializers

from audience.models import Audience
from integrations.models import Integration


class AudienceSerializer(serializers.ModelSerializer):
    integration_id = serializers.PrimaryKeyRelatedField(source="integration", queryset=Integration.objects.none(), required=False, allow_null=True)
    integration_name = serializers.CharField(source="integration.name", read_only=True, default="")
    submitted_at = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = Audience
        fields = ["id", "integration_id", "integration_name", "name", "mobile", "email", "zipcode", "city", "street", "state", "submitted_at", "created_at", "updated_at"]
        read_only_fields = ["id", "integration_name", "submitted_at", "created_at", "updated_at"]

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            fields["integration_id"].queryset = Integration.objects.filter(company=request.user.company)
        return fields
