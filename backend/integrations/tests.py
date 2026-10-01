from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from companies.models import Company
from integrations.models import Integration, IntegrationSubmission, IntegrationSubmissionLog


class IntegrationApiTests(APITestCase):
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
        self.list_url = reverse("integration_list_create")
        self.payload = {
            "name": "Lead intake",
            "fields": [
                {"name": "Full name", "field_type": "text", "required": True},
                {"name": "Budget", "field_type": "number"},
                {
                    "name": "Region",
                    "field_type": "select",
                    "options": ["North", "South"],
                },
            ],
        }

    def test_admin_can_create_list_update_and_delete_integration(self):
        self.client.force_authenticate(user=self.owner)

        create_response = self.client.post(self.list_url, self.payload, format="json")
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(create_response.data["fields"]), 3)
        self.assertTrue(
            create_response.data["form_url"].endswith(
                f"/integrations/public/{create_response.data['public_id']}"
            )
        )

        detail_url = reverse("integration_detail", kwargs={"pk": create_response.data["id"]})
        self.assertEqual(self.client.get(self.list_url).data["results"][0]["name"], "Lead intake")

        update_response = self.client.patch(
            detail_url,
            {"name": "Updated lead intake", "fields": [{"name": "Email", "field_type": "email"}]},
            format="json",
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data["name"], "Updated lead intake")
        self.assertEqual([field["name"] for field in update_response.data["fields"]], ["Email"])

        public_response = self.client.get(
            reverse("integration_public_form", kwargs={"public_id": update_response.data["public_id"]})
        )
        self.assertEqual(public_response.status_code, status.HTTP_200_OK)
        self.assertEqual(public_response.data["fields"][0]["field_type"], "email")

        submit_url = reverse(
            "integration_public_submit",
            kwargs={"public_id": update_response.data["public_id"]},
        )
        submit_response = self.client.post(submit_url, {"Email": "lead@northwind.test"}, format="json")
        self.assertEqual(submit_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(IntegrationSubmission.objects.count(), 1)
        second_submit = self.client.post(submit_url, {"Email": "lead@northwind.test"}, format="json")
        self.assertEqual(second_submit.status_code, status.HTTP_201_CREATED)
        self.assertEqual(IntegrationSubmission.objects.count(), 1)
        self.assertEqual(IntegrationSubmission.objects.get().data["Email"], "lead@northwind.test")
        self.assertEqual(IntegrationSubmissionLog.objects.filter(status="success").count(), 2)

        self.client.force_authenticate(user=self.owner)
        logs_response = self.client.get(reverse("integration_logs", kwargs={"pk": update_response.data["id"]}))
        self.assertEqual(logs_response.data["total_success"], 2)
        self.assertEqual(logs_response.data["total_errors"], 0)
        self.assertEqual(logs_response.data["count"], 2)
        self.assertEqual(len(logs_response.data["results"]), 2)
        one_log_response = self.client.get(
            reverse("integration_logs", kwargs={"pk": update_response.data["id"]}),
            {"page_size": 1},
        )
        self.assertEqual(one_log_response.data["count"], 2)
        self.assertEqual(len(one_log_response.data["results"]), 1)

        delete_response = self.client.delete(detail_url)
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Integration.objects.filter(name="Updated lead intake").exists())

    def test_integrations_are_isolated_by_company(self):
        Integration.objects.create(company=self.other_company, name="Other form")
        self.client.force_authenticate(user=self.owner)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"], [])
        self.assertEqual(response.data["count"], 0)

    def test_worker_cannot_manage_integrations(self):
        self.client.force_authenticate(user=self.worker)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_select_fields_require_options_and_field_names_are_unique(self):
        self.client.force_authenticate(user=self.owner)

        missing_options = {
            "name": "Invalid form",
            "fields": [{"name": "Region", "field_type": "select"}],
        }
        duplicate_names = {
            "name": "Duplicate fields",
            "fields": [
                {"name": "Contact", "field_type": "text"},
                {"name": "Contact", "field_type": "email"},
            ],
        }

        self.assertEqual(
            self.client.post(self.list_url, missing_options, format="json").status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            self.client.post(self.list_url, duplicate_names, format="json").status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_public_submission_requires_required_fields(self):
        integration = Integration.objects.create(company=self.company, name="Required form")
        integration.fields.create(name="Email", field_type="email", required=True)
        submit_url = reverse("integration_public_submit", kwargs={"public_id": integration.public_id})

        response = self.client.post(submit_url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Email", response.data)
        self.assertEqual(IntegrationSubmissionLog.objects.get().status, "error")
        self.assertIn("required", IntegrationSubmissionLog.objects.get().error_message)

    def test_same_email_updates_existing_record_even_when_phone_changes(self):
        integration = Integration.objects.create(company=self.company, name="Basic data form")
        integration.fields.create(name="Enter your phone number", field_type="text")
        integration.fields.create(name="Select your email", field_type="email", required=True)
        submit_url = reverse("integration_public_submit", kwargs={"public_id": integration.public_id})

        first = self.client.post(
            submit_url,
            {"Enter your phone number": "123", "Select your email": "person@example.com"},
            format="json",
        )
        second = self.client.post(
            submit_url,
            {"Enter your phone number": "456", "Select your email": "person@example.com"},
            format="json",
        )

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)
        self.assertEqual(IntegrationSubmission.objects.filter(integration=integration).count(), 1)
        self.assertEqual(
            IntegrationSubmission.objects.get(integration=integration).data["Enter your phone number"],
            "456",
        )