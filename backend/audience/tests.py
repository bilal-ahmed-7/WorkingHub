from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from companies.models import Company
from integrations.models import Integration, IntegrationSubmission


class AudienceApiTests(APITestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Northwind")
        self.other_company = Company.objects.create(name="Contoso")
        self.owner = User.objects.create_user(
            email="owner@northwind.test",
            password="Password123!",
            role=User.Roles.ADMIN,
            company=self.company,
        )
        self.worker = User.objects.create_user(
            email="worker@northwind.test",
            password="Password123!",
            role=User.Roles.WORKER,
            company=self.company,
        )
        self.integration = Integration.objects.create(company=self.company, name="Lead intake")
        self.submission = IntegrationSubmission.objects.create(
            integration=self.integration,
            data={"Email": "customer@northwind.test", "City": "Seattle"},
        )
        self.list_url = reverse("audience_list")

    def test_admin_can_read_form_submissions_as_audience(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]["integration_name"], "Lead intake")
        self.assertEqual(response.data[0]["data"]["Email"], "customer@northwind.test")
        self.assertEqual(self.client.post(self.list_url, {}, format="json").status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_audience_submissions_are_isolated_by_company(self):
        other_integration = Integration.objects.create(company=self.other_company, name="Other form")
        IntegrationSubmission.objects.create(integration=other_integration, data={"Email": "other@test.com"})
        self.client.force_authenticate(user=self.owner)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_worker_cannot_read_audience_submissions(self):
        self.client.force_authenticate(user=self.worker)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
