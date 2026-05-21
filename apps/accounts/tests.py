import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import Company, User


def _image_file(name="logo.png", size=(100, 50), color=(30, 136, 229)):
    buffer = io.BytesIO()
    image = Image.new("RGB", size=size, color=color)
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type="image/png")


class CompanyBrandingApiTests(APITestCase):
    def setUp(self):
        self.company_a = Company.objects.create(name="Acme Pvt Ltd", company_code="ACME001")
        self.company_b = Company.objects.create(name="Beta Pvt Ltd", company_code="BETA001")

        self.admin_a = User.objects.create_user(
            username="admina@example.com",
            email="admina@example.com",
            password="Admin@12345",
            role="ADMIN",
            company=self.company_a,
        )
        self.admin_b = User.objects.create_user(
            username="adminb@example.com",
            email="adminb@example.com",
            password="Admin@12345",
            role="ADMIN",
            company=self.company_b,
        )
        self.super_admin = User.objects.create_user(
            username="super@example.com",
            email="super@example.com",
            password="Super@12345",
            role="SUPER_ADMIN",
        )

    def test_company_admin_upload_replace_delete_logo_for_own_company(self):
        self.client.force_authenticate(self.admin_a)

        upload_res = self.client.post(
            "/api/accounts/company-branding/logo/",
            {"logo": _image_file("logo1.png")},
            format="multipart",
        )
        self.assertEqual(upload_res.status_code, status.HTTP_200_OK)
        self.assertTrue(upload_res.data.get("logo_url") or upload_res.data.get("logoUrl"))

        replace_res = self.client.post(
            "/api/accounts/company-branding/logo/",
            {"logo": _image_file("logo2.png", color=(220, 20, 60))},
            format="multipart",
        )
        self.assertEqual(replace_res.status_code, status.HTTP_200_OK)

        get_res = self.client.get("/api/accounts/company-branding/")
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)
        self.assertEqual(get_res.data.get("id"), self.company_a.id)
        self.assertTrue(get_res.data.get("logo_url") or get_res.data.get("logoUrl"))

        delete_res = self.client.delete("/api/accounts/company-branding/logo/")
        self.assertEqual(delete_res.status_code, status.HTTP_200_OK)
        self.assertIsNone(delete_res.data.get("logo_url"))

    def test_tenant_isolation_company_branding_returns_only_own_company(self):
        self.client.force_authenticate(self.admin_b)

        res = self.client.get("/api/accounts/company-branding/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data.get("id"), self.company_b.id)
        self.assertNotEqual(res.data.get("id"), self.company_a.id)

    def test_non_company_user_cannot_manage_company_branding(self):
        self.client.force_authenticate(self.super_admin)
        res = self.client.get("/api/accounts/company-branding/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
