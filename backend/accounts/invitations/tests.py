from datetime import timedelta
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from companies.models import Company
from accounts.invitations.models import Invitation


class InvitationsApiTests(APITestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Cyberdyne Systems")
        self.owner = User.objects.create_user(
            email="owner@cyberdyne.com",
            password="Password123!",
            role=User.Roles.ADMIN,
            company=self.company,
            first_name="Miles",
            last_name="Dyson",
        )

        self.send_url = reverse("send_invitation")
        self.list_url = reverse("invitation_list")
        self.accept_url = reverse("accept_invitation")

    def test_owner_send_invitation(self):
        self.client.force_authenticate(user=self.owner)
        payload = {"email": "worker@cyberdyne.com"}
        resp = self.client.post(self.send_url, payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn("invitation", resp.data)
        self.assertEqual(resp.data["invitation"]["email"], "worker@cyberdyne.com")

        # Verify invitation created in DB
        invitation = Invitation.objects.filter(email="worker@cyberdyne.com").first()
        self.assertIsNotNone(invitation)
        self.assertEqual(invitation.company, self.company)
        self.assertTrue(invitation.is_valid())

        # A dispatched invitation is not a team member until it is accepted.
        self.assertFalse(User.objects.filter(email="worker@cyberdyne.com").exists())

    def test_invitation_list_contains_only_pending_invitations(self):
        Invitation.objects.create(
            email="pending@cyberdyne.com",
            company=self.company,
            token="pending-token",
            expires_at=timezone.now() + timedelta(hours=24),
        )
        Invitation.objects.create(
            email="accepted@cyberdyne.com",
            company=self.company,
            token="accepted-token",
            is_accepted=True,
            expires_at=timezone.now() + timedelta(hours=24),
        )
        Invitation.objects.create(
            email="expired@cyberdyne.com",
            company=self.company,
            token="expired-token",
            expires_at=timezone.now() - timedelta(hours=1),
        )
        self.client.force_authenticate(user=self.owner)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["email"] for item in response.data["results"]], ["pending@cyberdyne.com"])

    def test_invitation_list_supports_dynamic_page_size(self):
        for index in range(2):
            Invitation.objects.create(
                email=f"pending{index}@cyberdyne.com",
                company=self.company,
                token=f"pending-token-{index}",
                expires_at=timezone.now() + timedelta(hours=24),
            )
        self.client.force_authenticate(user=self.owner)

        response = self.client.get(self.list_url, {"page_size": 1})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(len(response.data["results"]), 1)

    def test_validate_invitation_token(self):
        invitation = Invitation.objects.create(
            email="newjoiner@cyberdyne.com",
            company=self.company,
            token="test-token-12345",
            expires_at=timezone.now() + timedelta(hours=48),
        )

        validate_url = reverse("validate_invitation", kwargs={"token": "test-token-12345"})
        resp = self.client.get(validate_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["valid"])
        self.assertEqual(resp.data["email"], "newjoiner@cyberdyne.com")
        self.assertEqual(resp.data["company_name"], "Cyberdyne Systems")

    def test_accept_invitation_flow(self):
        invitation = Invitation.objects.create(
            email="newjoiner@cyberdyne.com",
            company=self.company,
            token="test-token-accept-999",
            expires_at=timezone.now() + timedelta(hours=48),
        )
        User.objects.create_user(
            email="newjoiner@cyberdyne.com",
            role=User.Roles.WORKER,
            company=self.company,
        )

        payload = {
            "token": "test-token-accept-999",
            "first_name": "John",
            "last_name": "Connor",
            "new_password": "NewPermanentPassword123!",
            "confirm_new_password": "NewPermanentPassword123!",
        }

        resp = self.client.post(self.accept_url, payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("tokens", resp.data)
        self.assertIn("access", resp.data["tokens"])
        self.assertEqual(resp.data["user"]["first_name"], "John")

        invitation.refresh_from_db()
        self.assertTrue(invitation.is_accepted)

        worker = User.objects.get(email="newjoiner@cyberdyne.com")
        self.assertTrue(worker.check_password("NewPermanentPassword123!"))
        self.assertEqual(worker.first_name, "John")

    def test_accept_invitation_creates_worker_account(self):
        invitation = Invitation.objects.create(
            email="newworker@cyberdyne.com",
            company=self.company,
            token="test-token-new-worker-123",
            expires_at=timezone.now() + timedelta(hours=48),
        )

        self.assertFalse(User.objects.filter(email=invitation.email).exists())
        response = self.client.post(
            self.accept_url,
            {
                "token": invitation.token,
                "first_name": "New",
                "last_name": "Worker",
                "new_password": "NewPermanentPassword123!",
                "confirm_new_password": "NewPermanentPassword123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(User.objects.filter(email=invitation.email).exists())
