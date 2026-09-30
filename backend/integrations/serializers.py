from django.db import transaction
from django.conf import settings
from django.urls import reverse
from rest_framework import serializers

from integrations.models import Integration, IntegrationField, IntegrationSubmission, IntegrationSubmissionLog


class IntegrationFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = IntegrationField
        fields = ["id", "name", "field_type", "required", "options", "position"]
        read_only_fields = ["id"]

    def validate(self, attrs):
        field_type = attrs.get("field_type", getattr(self.instance, "field_type", None))
        options = attrs.get("options", getattr(self.instance, "options", []))
        if field_type in {
            IntegrationField.FieldTypes.SELECT,
            IntegrationField.FieldTypes.MULTI_SELECT,
        } and not options:
            raise serializers.ValidationError({"options": "This field type requires at least one option."})
        if field_type not in {
            IntegrationField.FieldTypes.SELECT,
            IntegrationField.FieldTypes.MULTI_SELECT,
        } and options:
            raise serializers.ValidationError({"options": "Options are only supported for select fields."})
        return attrs


class IntegrationSerializer(serializers.ModelSerializer):
    fields = IntegrationFieldSerializer(many=True, required=False)
    form_url = serializers.SerializerMethodField()

    class Meta:
        model = Integration
        fields = [
            "id",
            "name",
            "public_id",
            "is_active",
            "fields",
            "form_url",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "public_id", "created_at", "updated_at", "form_url"]

    def get_form_url(self, integration):
        return f"{settings.FRONTEND_URL.rstrip('/')}/integrations/public/{integration.public_id}"

    def validate_fields(self, fields):
        names = [field["name"] for field in fields]
        if len(names) != len(set(names)):
            raise serializers.ValidationError("Field names must be unique within an integration.")
        return fields

    @transaction.atomic
    def create(self, validated_data):
        fields_data = validated_data.pop("fields", [])
        integration = Integration.objects.create(**validated_data)
        IntegrationField.objects.bulk_create(
            [IntegrationField(integration=integration, **field) for field in fields_data]
        )
        return integration

    @transaction.atomic
    def update(self, instance, validated_data):
        fields_data = validated_data.pop("fields", None)
        for attribute, value in validated_data.items():
            setattr(instance, attribute, value)
        instance.save()
        if fields_data is not None:
            instance.fields.all().delete()
            IntegrationField.objects.bulk_create(
                [IntegrationField(integration=instance, **field) for field in fields_data]
            )
        return instance


class IntegrationSubmissionSerializer(serializers.ModelSerializer):
    integration_name = serializers.CharField(source="integration.name", read_only=True)

    class Meta:
        model = IntegrationSubmission
        fields = ["id", "integration_name", "data", "submitted_at", "updated_at"]
        read_only_fields = fields


class IntegrationSubmissionLogSerializer(serializers.ModelSerializer):
    integration_name = serializers.CharField(source="integration.name", read_only=True)

    class Meta:
        model = IntegrationSubmissionLog
        fields = ["id", "integration_name", "data", "status", "error_message", "submitted_at"]
        read_only_fields = fields