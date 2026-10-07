from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from audience.models import Audience
from companies.models import Company
from integrations.models import Integration, IntegrationField, IntegrationSubmission, IntegrationSubmissionLog


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
            role=User.Roles.MEMBER,
            company=self.company,
        )
        self.list_url = reverse("integration_list_create")
        self.payload = {
            "name": "Lead intake",
            "fields": [
                {
                    "name": "Full name",
                    "field_type": "text",
                    "required": True,
                },
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
        self.assertEqual(len(create_response.data["fields"]), 5)
        self.assertEqual(
            [(field["system_key"], field["field_type"], field["required"]) for field in create_response.data["fields"][:2]],
            [("email", "email", True), ("phone", "number", True)],
        )
        self.assertTrue(
            create_response.data["form_url"].endswith(
                f"/integrations/public/{create_response.data['public_id']}"
            )
        )
        public_before_update = self.client.get(
            reverse(
                "integration_public_form",
                kwargs={"public_id": create_response.data["public_id"]},
            )
        )
        self.assertEqual(len(public_before_update.data["fields"]), 5)

        detail_url = reverse("integration_detail", kwargs={"pk": create_response.data["id"]})
        self.assertEqual(self.client.get(self.list_url).data["results"][0]["name"], "Lead intake")

        update_response = self.client.patch(
            detail_url,
            {
                "name": "Updated lead intake",
                "fields": [{"name": "Email", "field_type": "email"}],
            },
            format="json",
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data["name"], "Updated lead intake")
        self.assertEqual(
            [(field["name"], field["system_key"]) for field in update_response.data["fields"]],
            [("Email", "email"), ("Phone number", "phone")],
        )

        public_response = self.client.get(
            reverse("integration_public_form", kwargs={"public_id": update_response.data["public_id"]})
        )
        self.assertEqual(public_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [(field["system_key"], field["field_type"]) for field in public_response.data["fields"]],
            [("email", "email"), ("phone", "number")],
        )

        submit_url = reverse(
            "integration_public_submit",
            kwargs={"public_id": update_response.data["public_id"]},
        )
        submit_response = self.client.post(
            submit_url,
            {"email": "lead@northwind.test", "phone": "15550000001"},
            format="json",
        )
        self.assertEqual(submit_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(IntegrationSubmission.objects.count(), 1)
        second_submit = self.client.post(
            submit_url,
            {"email": "lead@northwind.test", "phone": "15550000002"},
            format="json",
        )
        self.assertEqual(second_submit.status_code, status.HTTP_201_CREATED)
        self.assertNotEqual(submit_response.data["submission_id"], second_submit.data["submission_id"])
        self.assertEqual(IntegrationSubmission.objects.count(), 2)
        self.assertEqual(
            IntegrationSubmission.objects.order_by("-id").first().data["phone"],
            "15550000002",
        )
        self.assertEqual(
            IntegrationSubmission.objects.order_by("-id").first().data["email"],
            "lead@northwind.test",
        )
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
        integration.fields.create(
            name="Email",
            field_type="email",
            system_key="email",
            required=False,
        )
        integration.fields.create(
            name="Phone number",
            field_type="number",
            system_key="phone",
            required=False,
        )
        submit_url = reverse("integration_public_submit", kwargs={"public_id": integration.public_id})

        response = self.client.post(submit_url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data,
            {
                "email": "Please enter your email address.",
                "phone": "Please enter your phone number.",
            },
        )
        self.assertEqual(IntegrationSubmissionLog.objects.get().status, "error")
        self.assertEqual(
            IntegrationSubmissionLog.objects.get().error_message,
            "Failed to save response.",
        )

    def test_submission_log_uses_generic_error_for_invalid_fields(self):
        integration = Integration.objects.create(company=self.company, name="Invalid payload form")
        integration.fields.create(name="Phone number", field_type="text")
        integration.fields.create(name="Email", field_type="email")

        response = self.client.post(
            reverse("integration_public_submit", kwargs={"public_id": integration.public_id}),
            {
                "Phone number": "15551234567",
                "Email": "invalid@example.com",
                "unexpected": "value",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "The form contains an invalid field.")
        log = IntegrationSubmissionLog.objects.get(integration=integration)
        self.assertEqual(log.error_message, "Failed to save response.")

    def test_new_integrations_keep_identifiers_required_and_exclude_them_from_custom_fields(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(self.list_url, {
            "name": "Identifier form",
            "fields": [
                {"name": "email address", "field_type": "text", "required": False},
                {"name": "Mobile", "field_type": "text", "required": False},
                {"name": "Comment", "field_type": "textarea"},
            ],
        }, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            [(field["name"], field["field_type"], field["system_key"], field["required"])
             for field in response.data["fields"][:2]],
            [("Email", "email", "email", True), ("Phone number", "number", "phone", True)],
        )
        self.assertEqual([field["name"] for field in response.data["fields"][2:]], ["Comment"])

    def test_address_autocomplete_creates_system_fields_and_uses_stable_submission_keys(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(self.list_url, {
            "name": "Address intake",
            "fields": [{"name": "Home address", "field_type": "address_autocomplete"}],
        }, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            [field["system_key"] for field in response.data["fields"]],
            ["email", "phone", "address_main", "address_street", "address_city", "address_zipcode", "address_state"],
        )
        self.assertTrue(response.data["fields"][0]["required"])
        self.assertTrue(response.data["fields"][1]["required"])
        self.assertTrue(response.data["fields"][4]["config"]["is_read_only"])

        submit_url = reverse("integration_public_submit", kwargs={"public_id": response.data["public_id"]})
        payload = {
            "email": "home@example.com",
            "phone": "15551234567",
            "address_main": "123 Main St, Seattle, WA 98101",
            "address_street": "123 Main St",
            "address_city": "Seattle",
            "address_zipcode": "98101",
            "address_state": "Austria",
        }
        self.assertEqual(self.client.post(submit_url, payload, format="json").status_code, status.HTTP_201_CREATED)
        self.assertEqual(IntegrationSubmission.objects.get().data, payload)
        self.assertEqual(Audience.objects.get().state, "Austria")

    def test_old_address_form_accepts_address_state_from_current_public_form(self):
        integration = Integration.objects.create(company=self.company, name="Legacy address form")
        integration.fields.create(
            name="Email",
            field_type="email",
            system_key=IntegrationField.SystemKeys.EMAIL,
            required=True,
        )
        integration.fields.create(
            name="Phone number",
            field_type="number",
            system_key=IntegrationField.SystemKeys.PHONE,
            required=True,
        )
        integration.fields.create(
            name="Address",
            field_type="address_autocomplete",
            system_key=IntegrationField.SystemKeys.ADDRESS_MAIN,
            required=True,
        )
        integration.fields.create(
            name="Street",
            field_type="text",
            system_key=IntegrationField.SystemKeys.ADDRESS_STREET,
            config={"is_read_only": True},
        )
        integration.fields.create(
            name="City",
            field_type="text",
            system_key=IntegrationField.SystemKeys.ADDRESS_CITY,
            config={"is_read_only": True},
        )
        integration.fields.create(
            name="ZIP Code",
            field_type="text",
            system_key=IntegrationField.SystemKeys.ADDRESS_ZIPCODE,
            config={"is_read_only": True},
        )
        submit_url = reverse(
            "integration_public_submit",
            kwargs={"public_id": integration.public_id},
        )
        payload = {
            "email": "legacy@example.com",
            "phone": "15551234567",
            "address_main": "Hausweingarten 923, 2145 Hausbrunn, Austria",
            "address_street": "Hausweingarten 923",
            "address_city": "Hausbrunn",
            "address_zipcode": "2145",
            "address_state": "Austria",
        }

        response = self.client.post(submit_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(IntegrationSubmission.objects.get(integration=integration).data["address_state"], "Austria")
        self.assertEqual(Audience.objects.get(integration=integration).state, "Austria")

    def test_manual_address_fields_populate_audience_from_form_submission(self):
        integration = Integration.objects.create(company=self.company, name="Manual address form")
        integration.fields.create(
            name="Email",
            field_type="email",
            system_key=IntegrationField.SystemKeys.EMAIL,
            required=True,
        )
        integration.fields.create(
            name="Phone number",
            field_type="number",
            system_key=IntegrationField.SystemKeys.PHONE,
            required=True,
        )
        for name in ("Your street address", "Your city", "ZIP", "State / Province"):
            integration.fields.create(
                name=name,
                field_type="text",
                system_key=IntegrationField.SystemKeys.CUSTOM,
            )
        submit_url = reverse(
            "integration_public_submit",
            kwargs={"public_id": integration.public_id},
        )

        response = self.client.post(
            submit_url,
            {
                "email": "manual@example.com",
                "phone": "15551234567",
                "Your street address": "12 Main Street",
                "Your city": "Hausbrunn",
                "ZIP": "2145",
                "State / Province": "Austria",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        record = Audience.objects.get(integration=integration)
        self.assertEqual(record.street, "12 Main Street")
        self.assertEqual(record.city, "Hausbrunn")
        self.assertEqual(record.zipcode, "2145")
        self.assertEqual(record.state, "Austria")

    def test_public_address_only_form_returns_one_visible_field(self):
        self.client.force_authenticate(user=self.owner)
        created = self.client.post(self.list_url, {
            "name": "Address only",
            "fields": [{"name": "Address", "field_type": "address_autocomplete"}],
        }, format="json")
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(created.data["fields"]), 7)

        public_form = self.client.get(reverse(
            "integration_public_form",
            kwargs={"public_id": created.data["public_id"]},
        ))

        self.assertEqual(public_form.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [field["system_key"] for field in public_form.data["fields"]],
            ["email", "phone", "address_main"],
        )

    def test_address_autocomplete_rejects_conflicting_manual_children(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(self.list_url, {
            "name": "Invalid address intake",
            "fields": [
                {"name": "Address", "field_type": "address_autocomplete"},
                {"name": "City", "field_type": "text"},
            ],
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_public_form_hides_system_address_children(self):
        integration = Integration.objects.create(company=self.company, name="Address intake")
        integration.fields.create(name="Mobile", field_type="text", required=True, system_key="custom")
        integration.fields.create(name="Email", field_type="email", required=True, system_key="custom")
        integration.fields.create(name="State", field_type="text", required=False, system_key="custom")
        parent = integration.fields.create(name="Address", field_type="address_autocomplete", required=True, system_key="address_main")
        integration.fields.create(name="Street", field_type="text", system_key="address_street", config={"is_read_only": True})
        integration.fields.create(name="City", field_type="text", system_key="address_city", config={"is_read_only": True})
        integration.fields.create(name="ZIP Code", field_type="text", system_key="address_zipcode", config={"is_read_only": True})

        response = self.client.get(reverse("integration_public_form", kwargs={"public_id": integration.public_id}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["fields"]), 4)
        self.assertEqual([field["system_key"] for field in response.data["fields"]], ["custom", "custom", "custom", "address_main"])
        self.assertNotIn("address_street", [field["system_key"] for field in response.data["fields"]])

    def test_same_email_with_different_phone_creates_another_audience(self):
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
        self.assertEqual(
            second.data["message"],
            "Thanks, your response has been submitted.",
        )
        self.assertEqual(IntegrationSubmission.objects.filter(integration=integration).count(), 2)
        self.assertEqual(Audience.objects.filter(company=self.company).count(), 2)
        self.assertTrue(
            Audience.objects.filter(
                company=self.company,
                mobile="123",
                email="person@example.com",
            ).exists()
        )
        self.assertTrue(
            Audience.objects.filter(
                company=self.company,
                mobile="456",
                email="person@example.com",
            ).exists()
        )

    def test_public_form_rejects_phone_already_used_by_another_company(self):
        integration = Integration.objects.create(company=self.company, name="Phone conflict form")
        integration.fields.create(name="Phone number", field_type="text")
        integration.fields.create(name="Email", field_type="email")
        Audience.objects.create(
            company=self.other_company,
            mobile="1-555-888-1234",
            email="other@example.com",
        )

        response = self.client.post(
            reverse("integration_public_submit", kwargs={"public_id": integration.public_id}),
            {"Phone number": "+1 (555) 888-1234", "Email": "new@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("+1 (555) 888-1234", response.data["detail"])
        self.assertEqual(
            IntegrationSubmissionLog.objects.get(integration=integration).error_message,
            "Failed to save response.",
        )
        self.assertEqual(IntegrationSubmission.objects.filter(integration=integration).count(), 0)
        self.assertEqual(Audience.objects.filter(company=self.company).count(), 0)
        self.assertEqual(
            IntegrationSubmissionLog.objects.get(integration=integration).status,
            IntegrationSubmissionLog.Status.ERROR,
        )

    def test_same_phone_updates_earliest_submission(self):
        integration = Integration.objects.create(company=self.company, name="Phone identity form")
        integration.fields.create(name="Mobile", field_type="text")
        integration.fields.create(name="Email", field_type="email")
        first = IntegrationSubmission.objects.create(
            integration=integration,
            data={"Mobile": "+1 (555) 123-4567", "Email": "old@example.com"},
            identity_key="email:old@example.com",
        )
        later = IntegrationSubmission.objects.create(
            integration=integration,
            data={"Mobile": "15551234567", "Email": "duplicate@example.com"},
            identity_key="email:duplicate@example.com",
        )
        submit_url = reverse("integration_public_submit", kwargs={"public_id": integration.public_id})

        response = self.client.post(
            submit_url,
            {"Mobile": "1-555-123-4567", "Email": "new@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["submission_id"], first.id)
        self.assertEqual(IntegrationSubmission.objects.filter(integration=integration).count(), 2)
        first.refresh_from_db()
        later.refresh_from_db()
        self.assertEqual(first.data["Email"], "new@example.com")
        self.assertEqual(first.identity_key, "phone:15551234567")
        self.assertEqual(later.data["Email"], "duplicate@example.com")

    def test_resubmission_updates_earliest_audience_by_phone(self):
        integration = Integration.objects.create(company=self.company, name="Audience phone identity")
        integration.fields.create(name="Phone number", field_type="text")
        integration.fields.create(name="Email", field_type="email")
        first_audience = Audience.objects.create(
            company=self.company,
            integration=integration,
            mobile="+1 (555) 777-1234",
            email="first@example.com",
        )
        first = self.client.post(
            reverse("integration_public_submit", kwargs={"public_id": integration.public_id}),
            {"Phone number": "1-555-777-1234", "Email": "first@example.com"},
            format="json",
        )
        original = IntegrationSubmission.objects.get(pk=first.data["submission_id"])

        second = self.client.post(
            reverse("integration_public_submit", kwargs={"public_id": integration.public_id}),
            {"Phone number": "+1 (555) 777-1234", "Email": "updated@example.com"},
            format="json",
        )

        self.assertEqual(second.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            second.data["message"],
            "Thanks, your response has been submitted.",
        )
        self.assertEqual(second.data["submission_id"], original.id)
        self.assertEqual(IntegrationSubmission.objects.filter(integration=integration).count(), 1)
        self.assertEqual(
            Audience.objects.filter(company=self.company, integration=integration).count(),
            1,
        )
        first_audience.refresh_from_db()
        self.assertEqual(first_audience.email, "updated@example.com")
        self.assertEqual(first_audience.mobile, "15557771234")
