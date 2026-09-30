from django.db import models

from companies.models import Company


class Audience(models.Model):
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="audience",
    )
    name= models.CharField(max_length=255)
    mobile = models.CharField(max_length=32, unique=True)
    email = models.EmailField(unique=True)
    zipcode = models.CharField(max_length=20)
    city = models.CharField(max_length=120)
    street = models.CharField(max_length=255)
    state = models.CharField(max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["city", "email"]
        verbose_name_plural = "audience"

    def __str__(self) -> str:
        return f"{self.email} ({self.company.name})"
