from django.db import models
from django.conf import settings
from decimal import Decimal
from apps.employees.models import Employee


# ======================================================
# LEAVE TYPE CONFIGURATION (Company Level)
# ======================================================

class LeaveType(models.Model):

    name = models.CharField(max_length=100, unique=True)
    annual_quota = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    is_paid = models.BooleanField(default=True)

    carry_forward = models.BooleanField(default=False)
    max_carry_forward = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    requires_approval = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    encashable = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["is_active"]),
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
    


class LeaveAccrualLog(models.Model):
    employee = models.ForeignKey("employees.Employee", on_delete=models.CASCADE)
    leave_type = models.ForeignKey("leaves.LeaveType", on_delete=models.CASCADE)
    year = models.IntegerField()
    month = models.IntegerField()
    credited_days = models.DecimalField(max_digits=5, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("employee", "leave_type", "year", "month")

    def __str__(self):
        return f"{self.employee} - {self.leave_type.name} - {self.month}/{self.year}"


class Holiday(models.Model):

    name = models.CharField(max_length=100)

    date = models.DateField()

    description = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.date}"