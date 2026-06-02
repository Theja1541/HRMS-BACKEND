from django.db import models
from django.conf import settings
from decimal import Decimal
from apps.employees.models import Employee


# ======================================================
# LEAVE TYPE CONFIGURATION (Company Level)
# ======================================================

class LeaveType(models.Model):

    ACCRUAL_CHOICES = (
        ("ANNUAL", "Annual (All at once)"),
        ("MONTHLY", "Monthly Accrual"),
        ("QUARTERLY", "Quarterly Accrual"),
    )

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, default="DEFAULT") # Default will be replaced in migration
    company = models.ForeignKey(
        "accounts.Company", on_delete=models.CASCADE, null=True, blank=True, related_name="leave_types"
    )
    is_system_leave = models.BooleanField(default=False)
    annual_quota = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    is_paid = models.BooleanField(default=True)
    
    accrual_type = models.CharField(
        max_length=20,
        choices=ACCRUAL_CHOICES,
        default="ANNUAL",
        help_text="How leaves are credited to employees"
    )
    
    accrual_start_month = models.IntegerField(
        default=1,
        help_text="Month when accrual starts (1=Jan, 12=Dec)"
    )

    carry_forward = models.BooleanField(default=False)
    max_carry_forward = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    requires_approval = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    encashable = models.BooleanField(default=False)
    
    allow_negative_balance = models.BooleanField(
        default=False,
        help_text="Allow employees to take leave even if balance is insufficient (will become LOP)"
    )

    max_consecutive_days = models.PositiveIntegerField(null=True, blank=True)
    advance_notice_days = models.PositiveIntegerField(default=0)
    include_weekends = models.BooleanField(default=False)
    include_holidays = models.BooleanField(default=False)
    
    document_required = models.BooleanField(default=False)
    document_required_after_days = models.PositiveIntegerField(default=0)
    
    allowed_during_probation = models.BooleanField(default=True)
    prorate_for_new_joiners = models.BooleanField(default=True)
    
    GENDER_CHOICES = (
        ("ALL", "All"),
        ("MALE", "Male"),
        ("FEMALE", "Female"),
    )
    applicable_gender = models.CharField(max_length=10, choices=GENDER_CHOICES, default="ALL")
    applicable_employment_types = models.JSONField(default=list, blank=True)
    applicable_departments = models.JSONField(default=list, blank=True)
    applicable_designations = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['company', 'name'], name='unique_leave_name_per_company'),
            models.UniqueConstraint(fields=['company', 'code'], name='unique_leave_code_per_company'),
        ]
        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(fields=["company", "code"]),
        ]

    def __str__(self):
        return self.name


# ======================================================
# EMPLOYEE YEARLY LEAVE BALANCE
# ======================================================

class LeaveBalance(models.Model):

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        db_index=True
    )

    leave_type = models.ForeignKey(
        LeaveType,
        on_delete=models.CASCADE,
        db_index=True
    )

    year = models.IntegerField(db_index=True)

    total_allocated = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("0.00")
    )

    used = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("0.00")
    )

    class Meta:
        unique_together = ("employee", "leave_type", "year")
        indexes = [
            models.Index(fields=["employee", "year"]),
            models.Index(fields=["employee", "leave_type", "year"]),
        ]

    @property
    def remaining(self):
        return self.total_allocated - self.used

    def __str__(self):
        return f"{self.employee.employee_id} - {self.leave_type.name} - {self.year}"


# ======================================================
# LEAVE REQUEST
# ======================================================

class LeaveRequest(models.Model):

    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
        ("CANCELLED", "Cancelled"),
    )

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="leave_requests",
        db_index=True
    )

    leave_type = models.ForeignKey(
        LeaveType,
        on_delete=models.CASCADE,
        db_index=True
    )

    start_date = models.DateField(db_index=True)
    end_date = models.DateField(db_index=True)

    is_half_day = models.BooleanField(default=False)

    reason = models.TextField()

    document = models.FileField(upload_to="leave_documents/", null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING",
        db_index=True
    )

    applied_on = models.DateTimeField(auto_now_add=True)

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    approved_on = models.DateTimeField(null=True, blank=True)
    approval_trail = models.JSONField(default=list, blank=True)
    class Meta:
        indexes = [
            models.Index(fields=["employee", "status"]),
            models.Index(fields=["employee", "start_date"]),
            models.Index(fields=["employee", "end_date"]),
        ]

    def total_days(self):
        if self.is_half_day:
            return Decimal("0.5")
        return Decimal((self.end_date - self.start_date).days + 1)

    def __str__(self):
        return f"{self.employee.employee_id} - {self.leave_type.name} ({self.status})"


# ======================================================
# LEAVE APPROVAL LOG (AUDIT TRAIL)
# ======================================================

class LeaveApprovalLog(models.Model):

    leave_request = models.ForeignKey(
        LeaveRequest,
        on_delete=models.CASCADE,
        related_name="approval_logs"
    )

    action = models.CharField(max_length=50)

    performed_by = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True
    )

    performed_at = models.DateTimeField(auto_now_add=True)

    comments = models.TextField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["leave_request"]),
        ]

    def __str__(self):
        return f"{self.leave_request.id} - {self.action}"
    

