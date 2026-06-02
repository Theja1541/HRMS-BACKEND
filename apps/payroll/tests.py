import io
from datetime import date
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from django.test import TestCase

from apps.accounts.models import Company, User
from apps.employees.models import Employee
from apps.payroll.models import Payslip
from apps.payroll.utils.payslip_pdf import generate_payslip_pdf


def _logo_file(name="company-logo.png"):
    buffer = io.BytesIO()
    image = Image.new("RGB", size=(200, 100), color=(12, 85, 160))
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type="image/png")


class PayslipCompanyLogoTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Logo Co", company_code="LOGO001")
        self.user = User.objects.create_user(
            username="emp@example.com",
            email="emp@example.com",
            password="Emp@12345",
            role="EMPLOYEE",
            company=self.company,
        )
        self.employee = Employee.objects.create(
            user=self.user,
            employee_id="EMP001",
            first_name="Test",
            last_name="Employee",
            email="emp@example.com",
            mobile="9999999999",
            department="IT",
            designation="Engineer",
            joining_date=date(2024, 1, 1),
            is_active=True,
        )
        self.payslip = Payslip.objects.create(
            employee=self.employee,
            month=date(2026, 3, 1),
            basic=Decimal("30000"),
            da=Decimal("2000"),
            hra=Decimal("15000"),
            conveyance=Decimal("3000"),
            medical=Decimal("2500"),
            special_allowance=Decimal("5000"),
            gross_salary=Decimal("57500"),
            lop_days=Decimal("0"),
            lop_deduction=Decimal("0"),
            employee_pf=Decimal("3600"),
            employer_pf=Decimal("3600"),
            employee_esi=Decimal("200"),
            employer_esi=Decimal("200"),
            professional_tax=Decimal("200"),
            tds_amount=Decimal("2000"),
            fixed_deductions=Decimal("0"),
            net_pay=Decimal("51500"),
            status="APPROVED",
        )

    def test_generate_payslip_pdf_with_company_logo(self):
        self.company.logo.save("logo.png", _logo_file(), save=True)
        pdf_with_logo = generate_payslip_pdf(self.payslip)
        self.assertTrue(pdf_with_logo.startswith(b"%PDF"))

        self.company.logo = None
        self.company.save(update_fields=["logo", "updated_at"])
        pdf_without_logo = generate_payslip_pdf(self.payslip)
        self.assertTrue(pdf_without_logo.startswith(b"%PDF"))

        # Logo render path should alter generated PDF bytes (header object differences).
        self.assertNotEqual(pdf_with_logo, pdf_without_logo)
