from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from audience.models import Audience
from companies.models import Company


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
        self.list_url = reverse("audience_list_create")
        self.payload = {
            "mobile": "+1-206-555-0100",
            "email": "customer@northwind.test",
            "zipcode": "98101",
            "city": "Seattle",
            "street": "1st Avenue",
            "state": "Washington",
        }

    def test_admin_can_create_list_update_and_delete_audience(self):
        self.client.force_authenticate(user=self.owner)

        create_response = self.client.post(self.list_url, self.payload, format="json")
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_response.data["email"], self.payload["email"])

        detail_url = reverse("audience_detail", kwargs={"pk": create_response.data["id"]})
        self.assertEqual(self.client.get(self.list_url).data[0]["email"], self.payload["email"])

        update_response = self.client.patch(detail_url, {"city": "Bellevue"}, format="json")
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data["city"], "Bellevue")

        delete_response = self.client.delete(detail_url)
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Audience.objects.filter(email=self.payload["email"]).exists())

    def test_audience_records_are_isolated_by_company(self):
        Audience.objects.create(company=self.other_company, **self.payload)
        self.client.force_authenticate(user=self.owner)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_worker_cannot_access_audience_crud(self):
        self.client.force_authenticate(user=self.worker)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_email_and_mobile_must_be_unique(self):
        Audience.objects.create(company=self.company, **self.payload)
        self.client.force_authenticate(user=self.owner)

        duplicate_email = {**self.payload, "mobile": "+1-206-555-0101"}
        duplicate_mobile = {**self.payload, "email": "other@northwind.test"}

        self.assertEqual(
            self.client.post(self.list_url, duplicate_email, format="json").status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            self.client.post(self.list_url, duplicate_mobile, format="json").status_code,
            status.HTTP_400_BAD_REQUEST,
        )
