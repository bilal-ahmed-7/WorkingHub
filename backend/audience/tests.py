from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from audience.models import Audience
from audience.services import sync_audience_record
from companies.models import Company
from integrations.models import Integration


class AudienceApiTests(APITestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Northwind")
        self.other_company = Company.objects.create(name="Contoso")
        self.owner = User.objects.create_user(email="owner@northwind.test", password="Password123!", role=User.Roles.ADMIN, company=self.company)
        self.worker = User.objects.create_user(email="worker@northwind.test", password="Password123!", role=User.Roles.MEMBER, company=self.company)
        self.integration = Integration.objects.create(company=self.company, name="Lead intake")
        self.record = Audience.objects.create(company=self.company, integration=self.integration, name="Taylor Smith", mobile="5551234", email="taylor@northwind.test", zipcode="98101", city="Seattle", street="123 Main St", state="WA")
        self.list_url = reverse("audience_list")

    def test_admin_lists_standard_audience_schema(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data["results"][0]
        self.assertEqual(data["name"], "Taylor Smith")
        self.assertEqual(data["integration_name"], "Lead intake")
        self.assertNotIn("data", data)

    def test_create_update_delete_and_company_isolation(self):
        Audience.objects.create(company=self.other_company, name="Other", email="other@test.com")
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(self.list_url, {"name": "Alex", "email": "alex@test.com", "city": "Portland"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.client.get(self.list_url).data["count"], 2)
        detail_url = reverse("audience_detail", kwargs={"pk": response.data["id"]})
        self.assertEqual(self.client.patch(detail_url, {"city": "Seattle"}, format="json").status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.delete(detail_url).status_code, status.HTTP_204_NO_CONTENT)

    def test_sync_audience_record_creates_separate_record_per_submission(self):
        second_integration = Integration.objects.create(company=self.company, name="Partner form")
        first_record = Audience.objects.create(
            company=self.company,
            integration=self.integration,
            name="Taylor Smith",
            email="taylor@northwind.test",
            mobile="5551234",
        )

        sync_audience_record(second_integration, {"email": "taylor@northwind.test", "name": "Taylor Smith updated"})

        self.assertEqual(Audience.objects.filter(company=self.company).count(), 3)
        self.assertEqual(Audience.objects.filter(company=self.company, integration=self.integration).count(), 2)
        self.assertEqual(Audience.objects.filter(company=self.company, integration=second_integration).count(), 1)
        self.assertEqual(Audience.objects.get(pk=first_record.pk).name, "Taylor Smith")

    def test_sync_audience_record_does_not_update_existing(self):
        """Each submission creates a new record even within the same integration."""
        sync_audience_record(self.integration, {"email": "taylor@northwind.test", "name": "Taylor Re-submit"})

        self.assertEqual(
            Audience.objects.filter(company=self.company, integration=self.integration).count(), 2
        )

    def test_worker_cannot_access_audience(self):
        self.client.force_authenticate(user=self.worker)
        self.assertEqual(self.client.get(self.list_url).status_code, status.HTTP_403_FORBIDDEN)
