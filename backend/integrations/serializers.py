from django.db import transaction
from django.conf import settings
from django.urls import reverse
from rest_framework import serializers

from integrations.models import Integration, IntegrationField, IntegrationSubmission, IntegrationSubmissionLog
from integrations.field_registry import COMPOSITE_FIELD_GROUPS, ADDRESS_CHILDREN


class IntegrationFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = IntegrationField
        fields = [
            "id",
            "name",
            "field_type",
            "system_key",
            "config",
            "required",
            "options",
            "position",
        ]
        read_only_fields = ["id", "system_key", "config"]

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
        address_group = COMPOSITE_FIELD_GROUPS["address"]
        address_fields = [
            field for field in fields
            if field["field_type"] == address_group["parent_type"]
        ]
        if len(address_fields) > 1:
            raise serializers.ValidationError("Only one Address autocomplete field can be added to a form.")
        if address_fields:
            blocked = address_group["blocked_standalone_names"]
            conflicts = [
                field["name"] for field in fields
                if field["field_type"] != address_group["parent_type"]
                and field["name"].strip().lower() in blocked
            ]
            if conflicts:
                raise serializers.ValidationError(
                    "Remove manual address fields before adding Address autocomplete: "
                    + ", ".join(conflicts)
                )
        return fields

    @staticmethod
    def _create_fields(integration, fields_data):
        """Create user fields and any system-owned composite children together."""
        position = 0
        for field_data in sorted(fields_data, key=lambda field: field.get("position", 0)):
            is_address = field_data["field_type"] == IntegrationField.FieldTypes.ADDRESS_AUTOCOMPLETE
            parent = IntegrationField.objects.create(
                integration=integration,
                name=field_data["name"],
                field_type=field_data["field_type"],
                system_key=(
                    IntegrationField.SystemKeys.ADDRESS_MAIN
                    if is_address else IntegrationField.SystemKeys.CUSTOM
                ),
                config={},
                required=True if is_address else field_data.get("required", False),
                options=[] if is_address else field_data.get("options", []),
                position=position,
            )
            position += 1
            if is_address:
                for child_name, child_key in ADDRESS_CHILDREN:
                    IntegrationField.objects.create(
                        integration=integration,
                        name=child_name,
                        field_type=IntegrationField.FieldTypes.TEXT,
                        system_key=child_key,
                        config={"is_read_only": True, "auto_filled_by": parent.id},
                        required=False,
                        position=position,
                    )
                    position += 1

    @transaction.atomic
    def create(self, validated_data):
        fields_data = validated_data.pop("fields", [])
        integration = Integration.objects.create(**validated_data)
        self._create_fields(integration, fields_data)
        return integration

    @transaction.atomic
    def update(self, instance, validated_data):
        fields_data = validated_data.pop("fields", None)
        for attribute, value in validated_data.items():
            setattr(instance, attribute, value)
        instance.save()
        if fields_data is not None:
            instance.fields.all().delete()
            self._create_fields(instance, fields_data)
        return instance


class IntegrationSubmissionSerializer(serializers.ModelSerializer):
    integration_name = serializers.CharField(source="integration.name", read_only=True)

    class Meta:
        model = IntegrationSubmission
        fields = ["id", "integration_name", "data", "submitted_at", "updated_at"]
        read_only_fields = fields


class IntegrationSubmissionLogSerializer(serializers.ModelSerializer):
    integration_name = serializers.CharField(source="integration.name", read_only=True)
    form_id = serializers.IntegerField(source="integration.id", read_only=True)
    form_token = serializers.UUIDField(source="integration.public_id", read_only=True)

    class Meta:
        model = IntegrationSubmissionLog
        fields = [
            "id",
            "integration_name",
            "form_id",
            "form_token",
            "data",
            "status",
            "error_message",
            "request_meta",
            "response_status",
            "submitted_at",
        ]
        read_only_fields = fields
