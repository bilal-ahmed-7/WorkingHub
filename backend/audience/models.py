from django.db import models

from companies.models import Company
from integrations.models import Integration


class Audience(models.Model):
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="audience",
    )
    integration = models.ForeignKey(Integration, on_delete=models.SET_NULL, null=True, blank=True, related_name="audience_records")
    name = models.CharField(max_length=255, blank=True)
    mobile = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)
    zipcode = models.CharField(max_length=20, blank=True)
    city = models.CharField(max_length=120, blank=True)
    street = models.CharField(max_length=255, blank=True)
    state = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["city", "email"]
        verbose_name_plural = "audience"

    def __str__(self) -> str:
        return f"{self.email} ({self.company.name})"
