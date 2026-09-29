from django.db import models
from django.utils.translation import gettext_lazy as _


class Company(models.Model):
    """
    Tenant entity representing a distinct company organization.
    All users and invitations are scoped to a specific Company tenant.
    """

    name = models.CharField(max_length=255, verbose_name=_("Company Name"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))

    class Meta:
        verbose_name = _("Company")
        verbose_name_plural = _("Companies")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name
