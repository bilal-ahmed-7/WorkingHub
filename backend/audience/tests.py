from django.urls import reverse
from django.db import IntegrityError, transaction
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
        self.record = Audience.objects.create(company=self.company, integration=self.integration, name="Taylor Smith", mobile="202-555-0123", email="taylor@northwind.test", zipcode="98101", city="Seattle", street="123 Main St", state="WA")
        self.list_url = reverse("audience_list")

    def test_admin_lists_standard_audience_schema(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data["results"][0]
        self.assertEqual(data["name"], "Taylor Smith")
        self.assertEqual(data["integration_name"], "Lead intake")
        self.assertNotIn("data", data)

    def test_admin_can_sort_audience_records(self):
        Audience.objects.create(company=self.company, name="Zoe", mobile="5550001", email="zoe@northwind.test")
        Audience.objects.create(company=self.company, name="Alex", mobile="5550002", email="alex@northwind.test")
        self.client.force_authenticate(user=self.owner)

        response = self.client.get(self.list_url, {"ordering": "name"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [record["name"] for record in response.data["results"]],
            ["Alex", "Taylor Smith", "Zoe"],
        )

    def test_create_update_delete_and_company_isolation(self):
        Audience.objects.create(company=self.other_company, name="Other", mobile="5550003", email="other@test.com")
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(self.list_url, {"name": "Alex", "mobile": "202-555-0124", "email": "alex@test.com", "city": "Portland"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.client.get(self.list_url).data["count"], 2)
        detail_url = reverse("audience_detail", kwargs={"pk": response.data["id"]})
        self.assertEqual(self.client.patch(detail_url, {"city": "Seattle"}, format="json").status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.delete(detail_url).status_code, status.HTTP_204_NO_CONTENT)

    def test_update_requires_both_audience_identifiers(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.patch(
            reverse("audience_detail", kwargs={"pk": self.record.pk}),
            {"email": "", "mobile": ""},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.record.refresh_from_db()
        self.assertEqual(self.record.email, "taylor@northwind.test")
        self.assertEqual(self.record.mobile, "2025550123")

    def test_update_cannot_clear_either_required_identifier(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.patch(
            reverse("audience_detail", kwargs={"pk": self.record.pk}),
            {"email": ""},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.record.refresh_from_db()
        self.assertEqual(response.data["email"], ["Email is required."])
        self.assertEqual(self.record.email, "taylor@northwind.test")

    def test_create_requires_both_audience_identifiers(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(
            self.list_url,
            {"name": "No identifier"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Audience.objects.filter(name="No identifier").count(), 0)

    def test_mobile_accepts_only_supported_us_phone_formats(self):
        self.client.force_authenticate(user=self.owner)
        valid_numbers = (
            ("202-555-0124", "2025550124"),
            ("(202) 555-0125", "2025550125"),
            ("+12025550126", "12025550126"),
            ("202 555 0127", "2025550127"),
        )

        for index, (mobile, stored_mobile) in enumerate(valid_numbers):
            with self.subTest(mobile=mobile):
                response = self.client.post(
                    self.list_url,
                    {
                        "name": "Valid US number",
                        "mobile": mobile,
                        "email": f"valid-{index}@northwind.test",
                    },
                    format="json",
                )

                self.assertEqual(response.status_code, status.HTTP_201_CREATED)
                self.assertEqual(response.data["mobile"], stored_mobile)

    def test_updating_audience_phone_in_admin_display_format_succeeds(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.patch(
            reverse("audience_detail", kwargs={"pk": self.record.pk}),
            {"mobile": "202 555 0123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["mobile"], "2025550123")

    def test_mobile_rejects_invalid_us_formats_and_lengths(self):
        self.client.force_authenticate(user=self.owner)
        invalid_numbers = (
            "2025550123",
            "202-555-123",
            "+1202555012",
            "+442055501234",
            "(202)555-0123",
        )

        for index, mobile in enumerate(invalid_numbers):
            with self.subTest(mobile=mobile):
                response = self.client.post(
                    self.list_url,
                    {
                        "name": "Invalid number",
                        "mobile": mobile,
                        "email": f"invalid-{index}@northwind.test",
                    },
                    format="json",
                )

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertEqual(
                    response.data["mobile"],
                    [
                        "Enter a US phone number as (XXX) XXX-XXXX, "
                        "XXX-XXX-XXXX, or +1XXXXXXXXXX."
                    ],
                )

    def test_editing_record_to_an_existing_phone_returns_conflict(self):
        target = Audience.objects.create(
            company=self.company,
            integration=self.integration,
            name="Existing",
            mobile="202-555-0125",
            email="existing@example.com",
        )
        self.client.force_authenticate(user=self.owner)

        response = self.client.patch(
            reverse("audience_detail", kwargs={"pk": self.record.pk}),
            {"name": "Updated contact", "mobile": "202-555-0125", "email": "updated@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(
            "An audience with phone number 202-555-0125 already exists.",
            response.data["mobile"][0],
        )
        target.refresh_from_db()
        self.record.refresh_from_db()
        self.assertEqual(target.name, "Existing")
        self.assertEqual(target.email, "existing@example.com")
        self.assertEqual(self.record.mobile, "2025550123")
        self.assertEqual(Audience.objects.filter(company=self.company).count(), 2)

    def test_editing_phone_for_same_email_updates_existing_audience(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.patch(
            reverse("audience_detail", kwargs={"pk": self.record.pk}),
            {
                "name": "Taylor New Number",
                "mobile": "202-555-0126",
                "email": "TAYLOR@NORTHWIND.TEST",
                "city": "Portland",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.record.pk)
        self.assertEqual(Audience.objects.filter(company=self.company).count(), 1)
        self.record.refresh_from_db()
        self.assertEqual(self.record.mobile, "2025550126")
        self.assertEqual(self.record.email.casefold(), "taylor@northwind.test")
        self.assertEqual(self.record.name, "Taylor New Number")
        self.assertEqual(self.record.city, "Portland")

    def test_editing_phone_and_email_to_new_values_creates_separate_audience(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.patch(
            reverse("audience_detail", kwargs={"pk": self.record.pk}),
            {
                "name": "New Contact",
                "mobile": "202-555-0127",
                "email": "new@northwind.test",
                "city": "Portland",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotEqual(response.data["id"], self.record.pk)
        self.assertEqual(Audience.objects.filter(company=self.company).count(), 2)
        self.record.refresh_from_db()
        self.assertEqual(self.record.mobile, "2025550123")
        self.assertEqual(self.record.email, "taylor@northwind.test")
        new_record = Audience.objects.get(mobile="2025550127")
        self.assertEqual(new_record.name, "New Contact")
        self.assertEqual(new_record.email, "new@northwind.test")
        self.assertEqual(new_record.city, "Portland")

    def test_phone_identity_is_globally_unique_across_companies(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Audience.objects.create(
                    company=self.other_company,
                    mobile="202-555-0123",
                    email="duplicate@example.com",
                )

    def test_mobile_is_required_at_the_model_database_level(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Audience.objects.create(
                    company=self.company,
                    mobile="",
                    email="blank-phone@example.com",
                )

    def test_mobile_is_stored_in_normalized_form(self):
        record = Audience.objects.create(
            company=self.company,
            mobile="+1 (555) 987-6543",
            email="normalized@example.com",
        )

        self.assertEqual(record.mobile, "15559876543")

    def test_admin_create_with_existing_identifiers_updates_existing_record(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(
            self.list_url,
            {
                "name": "Taylor Updated",
                "mobile": "202-555-0123",
                "email": "TAYLOR@NORTHWIND.TEST",
                "city": "Portland",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.record.id)
        self.assertEqual(Audience.objects.filter(company=self.company).count(), 1)
        self.record.refresh_from_db()
        self.assertEqual(self.record.name, "Taylor Updated")
        self.assertEqual(self.record.city, "Portland")

    def test_sync_audience_record_updates_existing_record_across_integrations(self):
        second_integration = Integration.objects.create(company=self.company, name="Partner form")

        sync_audience_record(
            second_integration,
            {
                "email": "taylor@northwind.test",
                "phone": "202-555-0123",
                "name": "Taylor Smith updated",
            },
        )

        self.assertEqual(Audience.objects.filter(company=self.company).count(), 1)
        self.record.refresh_from_db()
        self.assertEqual(self.record.name, "Taylor Smith updated")
        self.assertEqual(self.record.integration, self.integration)

    def test_same_email_with_a_new_phone_creates_a_separate_audience(self):
        sync_audience_record(
            self.integration,
            {
                "email": "taylor@northwind.test",
                "phone": "202-555-0128",
                "name": "Taylor Re-submit",
            },
        )

        self.assertEqual(Audience.objects.filter(company=self.company).count(), 2)
        self.record.refresh_from_db()
        self.assertEqual(self.record.name, "Taylor Smith")
        self.assertTrue(
            Audience.objects.filter(
                company=self.company,
                mobile="2025550128",
                email="taylor@northwind.test",
            ).exists()
        )

    def test_worker_cannot_access_audience(self):
        self.client.force_authenticate(user=self.worker)
        self.assertEqual(self.client.get(self.list_url).status_code, status.HTTP_403_FORBIDDEN)
