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

    integration = models.ForeignKey(
        Integration,
        on_delete=models.CASCADE,
        related_name="fields",
    )
    name = models.CharField(max_length=120)
    field_type = models.CharField(max_length=20, choices=FieldTypes.choices)
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