from rest_framework import serializers

from audience.models import Audience
from audience.services import phone_identity
from integrations.models import Integration


class AudienceSerializer(serializers.ModelSerializer):
    integration_id = serializers.PrimaryKeyRelatedField(source="integration", queryset=Integration.objects.none(), required=False, allow_null=True)
    integration_name = serializers.CharField(source="integration.name", read_only=True, default="")
    submitted_at = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = Audience
        fields = ["id", "integration_id", "integration_name", "name", "mobile", "email", "zipcode", "city", "street", "state", "submitted_at", "created_at", "updated_at"]
        read_only_fields = ["id", "integration_name", "submitted_at", "created_at", "updated_at"]
        extra_kwargs = {"mobile": {"validators": []}}

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            fields["integration_id"].queryset = Integration.objects.filter(company=request.user.company)
        return fields

    def validate(self, attrs):
        email = attrs.get("email", self.instance.email if self.instance else "")
        mobile = attrs.get("mobile", self.instance.mobile if self.instance else "")
        errors = {}
        if not (email or "").strip():
            errors["email"] = "Email is required."
        if not (mobile or "").strip():
            errors["mobile"] = "Phone number is required."
        elif not phone_identity(mobile):
            errors["mobile"] = "Enter a valid phone number."
        else:
            identity = phone_identity(mobile)
            attrs["mobile"] = identity
            conflicts = Audience.objects.filter(mobile=identity)
            if self.instance:
                conflicts = conflicts.exclude(pk=self.instance.pk)
            company_id = getattr(
                getattr(self.context.get("request"), "user", None),
                "company_id",
                None,
            )
            conflict_exists = (
                conflicts.exists()
                if self.instance
                else conflicts.exclude(company_id=company_id).exists()
            )
            if conflict_exists:
                errors["mobile"] = (
                    f"An audience with phone number {mobile} already exists."
                )
        if errors:
            raise serializers.ValidationError(errors)
        return attrs
