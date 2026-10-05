import uuid
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Invitation(models.Model):
    """
    Represents an invitation token sent to prospective workers for tenant onboarding.
    Tokens expire after a set time window (default 48 hours).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(verbose_name=_("Member Email"))
    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="invitations",
        verbose_name=_("Company"),
    )
    token = models.CharField(
        max_length=64,
        unique=True,
        editable=False,
        verbose_name=_("Security Token"),
    )
    is_accepted = models.BooleanField(
        default=False,
        verbose_name=_("Is Accepted"),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At"),
    )
    expires_at = models.DateTimeField(
        verbose_name=_("Expires At"),
    )

    class Meta:
        verbose_name = _("Invitation")
        verbose_name_plural = _("Invitations")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Invite to {self.email} for {self.company.name}"

    def is_valid(self) -> bool:
        """
        Validates whether the invitation has not yet been accepted
        and has not expired past its expiration timestamp.
        """
        return not self.is_accepted and timezone.now() <= self.expires_at
