from django.db import models
from django.utils import timezone
from django.conf import settings
from django.core.validators import RegexValidator
# from apps.attendance.models import WorkCalendar, Shift

class Employee(models.Model):

    # ============================================================
    # LINKED USER (Optional – for Employee Portal Login)
    # ============================================================

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="employee_profile",
        null=True,
        blank=True
    )

    # ============================================================
    # MANUAL EMPLOYEE ID (Required + Unique)
    # ============================================================

    employee_id = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
    )

    # ============================================================
    # PERSONAL INFORMATION
    # ============================================================

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True)

    email = models.EmailField(unique=True, db_index=True)
    mobile = models.CharField(max_length=15)

    dob = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)

    blood_group = models.CharField(max_length=5, blank=True)
    nationality = models.CharField(max_length=100, blank=True)

    # ============================================================
    # JOB DETAILS
    # ============================================================

    department = models.CharField(max_length=100, db_index=True)
    designation = models.CharField(max_length=100)

    employment_type = models.CharField(
        max_length=50,
        default="Full-time"
    )

    joining_date = models.DateField()
    work_location = models.CharField(max_length=100, blank=True)
    reporting_manager = models.CharField(max_length=100, blank=True)

    EMPLOYMENT_STATUS_CHOICES = (
        ('ACTIVE', 'Active'),
        ('ONBOARDING', 'Onboarding'),
        ('PROBATION', 'Probation'),
        ('NOTICE_PERIOD', 'Notice Period'),
        ('RELIEVED', 'Relieved'),
        ('TERMINATED', 'Terminated'),
        ('RETIRED', 'Retired'),
    )

    employment_status = models.CharField(
        max_length=20,
        choices=EMPLOYMENT_STATUS_CHOICES,
        default='ACTIVE',
        db_index=True
    )

    # Soft delete
    is_active = models.BooleanField(default=True)
    # ============================================================
    # SALARY STRUCTURE
    # ============================================================

    # basic_salary = models.DecimalField(
    #     max_digits=12,
    #     decimal_places=2,
    #     default=0
    # )

    # allowances = models.DecimalField(
    #     max_digits=12,
    #     decimal_places=2,
    #     default=0
    # )

    # deductions = models.DecimalField(
    #     max_digits=12,
    #     decimal_places=2,
    #     default=0
    # )

    # ============================================================
    # COMPLIANCE (Indian Payroll Ready)
    # ============================================================

    pf_applicable = models.BooleanField(default=False)

    esi_applicable = models.BooleanField(default=False)
    esi_number = models.CharField(max_length=25, blank=True)

    pt_applicable = models.BooleanField(default=False)

    pan = models.CharField(max_length=15, blank=True)

    pf_number = models.CharField(max_length=50, blank=True, null=True)
    uan_number = models.CharField(max_length=50, blank=True, null=True)

    # ============================================================
    # BANK DETAILS
    # ============================================================

    bank_name = models.CharField(max_length=100, blank=True)
    account_number = models.CharField(max_length=30, blank=True)
    ifsc = models.CharField(max_length=20, blank=True)

    # ============================================================
    # DOCUMENTS
    # ============================================================

    profile_photo = models.ImageField(
            upload_to="employees/profile_photos/",
            null=True,
            blank=True
        )

    resume = models.FileField(
            upload_to="employees/resumes/",
            null=True,
            blank=True
        )

    offer_letter = models.FileField(
            upload_to="employees/offer_letters/",
            null=True,
            blank=True
        )

    aadhar_card = models.FileField(
            upload_to="employees/aadhar_cards/",
            null=True,
            blank=True
        )

    pan_card = models.FileField(
            upload_to="employees/pan_cards/",
            null=True,
            blank=True
        )

    address_proof = models.FileField(
            upload_to="employees/address_proofs/",
            null=True,
            blank=True
        )

    education_cert = models.FileField(
            upload_to="employees/education_certificates/",
            null=True,
            blank=True
        )

    experience_cert = models.FileField(
            upload_to="employees/experience_certificates/",
            null=True,
            blank=True
        )

    work_calendar = models.ForeignKey(
    "attendance.WorkCalendar",
    on_delete=models.SET_NULL,
    null=True,
    blank=True
)


    is_work_from_home = models.BooleanField(default=False)

    emergency_name = models.CharField(max_length=100, blank=True)
    emergency_number = models.CharField(max_length=15, blank=True)
    notes = models.TextField(blank=True)

    history = models.JSONField(default=list, blank=True)
    # ============================================================
    # TIMESTAMPS
    # ============================================================

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ============================================================
    # STRING REPRESENTATION
    # ============================================================

    def __str__(self):
        return f"{self.employee_id} - {self.first_name} {self.last_name}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    # ============================================================
    # META
    # ============================================================

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["employee_id"]),
            models.Index(fields=["email"]),
            models.Index(fields=["department"]),
        ]

# ============================================================
# EMPLOYEE HISTORY TRACKING
# ============================================================

# NOTE: EmployeeHistory model removed – migrated to Employee.history JSONField.



# NOTE: CustomRole model removed – role definitions now stored in JSONField `custom_roles`.



# NOTE: CustomDepartment model removed – department definitions now stored in JSONField `departments`.

# Placeholder models for compatibility with legacy code
class CustomRole(models.Model):
    """Simple role model retained for compatibility; stores role name per company."""
    name = models.CharField(max_length=100)
    company = models.ForeignKey(
        "accounts.Company",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="custom_roles",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.company.name if self.company else 'Global'})"

class CustomDepartment(models.Model):
    """Simple department model retained for compatibility; stores department name per company."""
    name = models.CharField(max_length=100)
    company = models.ForeignKey(
        "accounts.Company",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="custom_departments",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.company.name if self.company else 'Global'})"