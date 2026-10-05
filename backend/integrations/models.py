import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _

from companies.models import Company


class Integration(models.Model):
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="integrations",
    )
    name = models.CharField(max_length=255)
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "name"],
                name="unique_integration_name_per_company",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class IntegrationField(models.Model):
    class FieldTypes(models.TextChoices):
        TEXT = "text", _("Text")
        TEXTAREA = "textarea", _("Text area")
        NUMBER = "number", _("Number")
        EMAIL = "email", _("Email")
        DATE = "date", _("Date")
        SELECT = "select", _("Select")
        MULTI_SELECT = "multi_select", _("Multiple select")
        CHECKBOX = "checkbox", _("Checkbox")
        ADDRESS_AUTOCOMPLETE = "address_autocomplete", _("Address autocomplete")

    class SystemKeys(models.TextChoices):
        CUSTOM = "custom", _("Custom field")
        ADDRESS_MAIN = "address_main", _("Main address")
        ADDRESS_STREET = "address_street", _("Street")
        ADDRESS_CITY = "address_city", _("City")
        ADDRESS_ZIPCODE = "address_zipcode", _("ZIP code")

    integration = models.ForeignKey(
        Integration,
        on_delete=models.CASCADE,
        related_name="fields",
    )
    name = models.CharField(max_length=120)
    field_type = models.CharField(max_length=20, choices=FieldTypes.choices)
    system_key = models.CharField(
        max_length=50,
        choices=SystemKeys.choices,
        default=SystemKeys.CUSTOM,
    )
    config = models.JSONField(default=dict, blank=True)
    required = models.BooleanField(default=False)
    options = models.JSONField(default=list, blank=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["integration", "name"],
                name="unique_integration_field_name",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.integration.name}: {self.name}"


class IntegrationSubmission(models.Model):
    integration = models.ForeignKey(
        Integration,
        on_delete=models.CASCADE,
        related_name="submissions",
    )
    data = models.JSONField(default=dict)
    identity_key = models.CharField(max_length=255, blank=True, db_index=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-submitted_at"]

    def __str__(self) -> str:
        return f"{self.integration.name} submission {self.pk}"


class IntegrationSubmissionLog(models.Model):
    class Status(models.TextChoices):
        SUCCESS = "success", "Success"
        ERROR = "error", "Error"

    integration = models.ForeignKey(
        Integration,
        on_delete=models.CASCADE,
        related_name="submission_logs",
    )
    data = models.JSONField(default=dict)
    identity_key = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices)
    error_message = models.TextField(blank=True)
    request_meta = models.JSONField(default=dict)
    response_status = models.PositiveSmallIntegerField(default=201)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-submitted_at"]

    def __str__(self) -> str:
        return f"{self.integration.name} {self.status} attempt {self.pk}"
