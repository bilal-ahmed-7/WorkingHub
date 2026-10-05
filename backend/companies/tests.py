from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from companies.models import Company


class CompaniesApiTests(APITestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Stark Industries")
        self.other_company = Company.objects.create(name="Wayne Enterprises")

        self.owner = User.objects.create_user(
            email="tony@stark.com",
            password="Password123!",
            role=User.Roles.ADMIN,
            company=self.company,
            first_name="Tony",
            last_name="Stark",
        )

        self.worker = User.objects.create_user(
            email="peter@stark.com",
            password="Password123!",
            role=User.Roles.MEMBER,
            company=self.company,
            first_name="Peter",
            last_name="Parker",
        )

        self.other_worker = User.objects.create_user(
            email="bruce@wayne.com",
            password="Password123!",
            role=User.Roles.MEMBER,
            company=self.other_company,
            first_name="Bruce",
            last_name="Wayne",
        )

        self.company_detail_url = reverse("company_detail")
        self.stats_url = reverse("company_dashboard_stats")
        self.workers_list_url = reverse("company_workers_list")

    def test_owner_get_company_detail(self):
        self.client.force_authenticate(user=self.owner)
        resp = self.client.get(self.company_detail_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["name"], "Stark Industries")

    def test_owner_update_company_name(self):
        self.client.force_authenticate(user=self.owner)
        resp = self.client.patch(self.company_detail_url, {"name": "Stark Tech"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.company.refresh_from_db()
        self.assertEqual(self.company.name, "Stark Tech")

    def test_worker_cannot_update_company(self):
        self.client.force_authenticate(user=self.worker)
        resp = self.client.patch(self.company_detail_url, {"name": "Hacked Tech"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_dashboard_stats(self):
        self.client.force_authenticate(user=self.owner)
        resp = self.client.get(self.stats_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["is_admin"])
        self.assertEqual(resp.data["metrics"]["total_workers"], 1)

    def test_worker_dashboard_stats(self):
        self.client.force_authenticate(user=self.worker)
        resp = self.client.get(self.stats_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data["is_admin"])
        self.assertIn("colleagues_count", resp.data["metrics"])

    def test_owner_list_workers_tenant_isolated(self):
        self.client.force_authenticate(user=self.owner)
        resp = self.client.get(self.workers_list_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        emails = [w["email"] for w in resp.data["results"]]
        self.assertIn("peter@stark.com", emails)
        self.assertNotIn("bruce@wayne.com", emails)

    def test_worker_can_list_members_of_own_company(self):
        self.client.force_authenticate(user=self.worker)

        response = self.client.get(self.workers_list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        emails = [member["email"] for member in response.data["results"]]
        self.assertIn("peter@stark.com", emails)
        self.assertNotIn("bruce@wayne.com", emails)

    def test_owner_list_hides_unaccepted_placeholder_users(self):
        User.objects.create_user(
            email="pending@stark.com",
            role=User.Roles.MEMBER,
            company=self.company,
        )
        self.client.force_authenticate(user=self.owner)

        resp = self.client.get(self.workers_list_url)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        emails = [worker["email"] for worker in resp.data["results"]]
        self.assertNotIn("pending@stark.com", emails)

    def test_workers_page_size_and_search_are_applied(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.get(
            self.workers_list_url,
            {"search": "peter", "page_size": 1},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["email"], "peter@stark.com")

    def test_owner_delete_worker(self):
        self.client.force_authenticate(user=self.owner)
        delete_url = reverse("company_worker_delete", kwargs={"pk": self.worker.pk})
        resp = self.client.delete(delete_url)
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(User.objects.filter(email="peter@stark.com").exists())

    def test_owner_can_deactivate_worker_without_removing_member(self):
        self.client.force_authenticate(user=self.owner)
        status_url = reverse("company_worker_status", kwargs={"pk": self.worker.pk})

        resp = self.client.patch(status_url, {"is_active": False}, format="json")

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data["is_active"])
        self.worker.refresh_from_db()
        self.assertFalse(self.worker.is_active)
        self.assertTrue(User.objects.filter(pk=self.worker.pk).exists())

        members_response = self.client.get(self.workers_list_url)
        self.assertEqual(members_response.status_code, status.HTTP_200_OK)
        worker_data = next(member for member in members_response.data["results"] if member["id"] == self.worker.pk)
        self.assertFalse(worker_data["is_active"])

    def test_cannot_delete_other_company_worker(self):
        self.client.force_authenticate(user=self.owner)
        delete_url = reverse("company_worker_delete", kwargs={"pk": self.other_worker.pk})
        resp = self.client.delete(delete_url)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
