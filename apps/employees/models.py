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
    uan_number = models.CharField(max_length=25, blank=True)

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

    id_proof = models.FileField(
        upload_to="employees/id_proofs/",
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

    shift = models.ForeignKey(
    "attendance.Shift",
    on_delete=models.SET_NULL,
    null=True,
    blank=True
)

    is_work_from_home = models.BooleanField(default=False)

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

class EmployeeHistory(models.Model):

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="history"
    )

    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )

    field_name = models.CharField(max_length=100)
    old_value = models.TextField(null=True, blank=True)
    new_value = models.TextField(null=True, blank=True)

    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-changed_at"]

    def __str__(self):
        return f"{self.employee.employee_id} - {self.field_name} changed"