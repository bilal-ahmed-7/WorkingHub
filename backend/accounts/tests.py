from django.urls import reverse
from django.core import mail
from rest_framework import status
from rest_framework.test import APITestCase
from django.test import override_settings

from accounts.models import User
from companies.models import Company


class AccountsAuthTests(APITestCase):
    def setUp(self):
        self.register_url = reverse("register_owner")
        self.login_url = reverse("token_obtain_pair")
        self.refresh_url = reverse("token_refresh")
        self.me_url = reverse("user_profile")
        self.change_password_url = reverse("change_password")

    def test_owner_registration_success(self):
        payload = {
            "company_name": "Apex Innovations",
            "first_name": "John",
            "last_name": "Doe",
            "email": "owner@apex.com",
            "password": "StrongPassword123!",
            "confirm_password": "StrongPassword123!",
        }
        response = self.client.post(self.register_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("tokens", response.data)
        self.assertIn("access", response.data["tokens"])
        self.assertIn("refresh", response.data["tokens"])
        self.assertEqual(response.data["user"]["email"], "owner@apex.com")
        self.assertEqual(response.data["user"]["role"], "ADMIN")
        self.assertTrue(Company.objects.filter(name="Apex Innovations").exists())
        self.assertTrue(User.objects.filter(email="owner@apex.com").exists())

    def test_owner_registration_duplicate_email(self):
        Company.objects.create(name="Exist Corp")
        User.objects.create_user(email="test@exist.com", password="password123")

        payload = {
            "company_name": "Another Corp",
            "first_name": "Alice",
            "last_name": "Smith",
            "email": "test@exist.com",
            "password": "StrongPassword123!",
            "confirm_password": "StrongPassword123!",
        }
        response = self.client.post(self.register_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_owner_registration_sends_welcome_email(self):
        payload = {
            "company_name": "Welcome Corp",
            "first_name": "Wendy",
            "last_name": "Owner",
            "email": "wendy@welcome.test",
            "password": "StrongPassword123!",
            "confirm_password": "StrongPassword123!",
        }

        response = self.client.post(self.register_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["wendy@welcome.test"])
        self.assertIn("Welcome to WorkHub", mail.outbox[0].subject)
        self.assertIn("Welcome Corp", mail.outbox[0].body)

    def test_jwt_login_and_token_refresh(self):
        company = Company.objects.create(name="Apex Corp")
        user = User.objects.create_user(
            email="user@apex.com",
            password="StrongPassword123!",
            first_name="Jane",
            last_name="Doe",
            company=company,
            role=User.Roles.ADMIN,
        )

        login_payload = {
            "email": "user@apex.com",
            "password": "StrongPassword123!",
        }
        login_resp = self.client.post(self.login_url, login_payload, format="json")
        self.assertEqual(login_resp.status_code, status.HTTP_200_OK)
        self.assertIn("access", login_resp.data)
        self.assertIn("refresh", login_resp.data)
        self.assertEqual(login_resp.data["user"]["email"], "user@apex.com")

        # Test Token Refresh (Session Updation)
        refresh_token = login_resp.data["refresh"]
        refresh_resp = self.client.post(self.refresh_url, {"refresh": refresh_token}, format="json")
        self.assertEqual(refresh_resp.status_code, status.HTTP_200_OK)
        self.assertIn("access", refresh_resp.data)

    def test_inactive_account_gets_deactivation_login_message(self):
        user = User.objects.create_user(
            email="inactive@apex.com",
            password="StrongPassword123!",
            is_active=False,
        )

        response = self.client.post(
            self.login_url,
            {"email": user.email, "password": "StrongPassword123!"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(
            "Your account has been deactivated by admin. Contact administration.",
            response.data["non_field_errors"],
        )

    def test_get_and_update_profile(self):
        company = Company.objects.create(name="Apex Corp")
        user = User.objects.create_user(
            email="user@apex.com",
            password="StrongPassword123!",
            first_name="Jane",
            last_name="Doe",
            company=company,
        )

        # Authenticate
        self.client.force_authenticate(user=user)

        # GET Profile
        resp = self.client.get(self.me_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["email"], "user@apex.com")

        # Update Profile
        update_resp = self.client.patch(self.me_url, {"first_name": "Janet"}, format="json")
        self.assertEqual(update_resp.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertEqual(user.first_name, "Janet")
