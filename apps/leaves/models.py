from django.db import models
from django.utils import timezone
from apps.employees.models import Employee


# ======================================================
# LEAVE TYPE CONFIGURATION (Company Level)
# ======================================================

class LeaveType(models.Model):

    name = models.CharField(max_length=100, unique=True)

    annual_quota = models.IntegerField(default=0)

    is_paid = models.BooleanField(default=True)

    carry_forward = models.BooleanField(default=False)
    max_carry_forward = models.IntegerField(default=0)

    requires_approval = models.BooleanField(default=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    encashable = models.BooleanField(default=False)

    def __str__(self):
        return self.name

# ======================================================
# EMPLOYEE YEARLY LEAVE BALANCE
# ======================================================

class LeaveBalance(models.Model):
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE)
    balance = models.DecimalField(max_digits=5, decimal_places=1, default=0)

    year = models.IntegerField()

    total_allocated = models.FloatField(default=0)
    used = models.FloatField(default=0)

    class Meta:
        unique_together = ("employee", "leave_type", "year")

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
        related_name="leave_requests"
    )

    leave_type = models.ForeignKey(
        LeaveType,
        on_delete=models.CASCADE
    )

    start_date = models.DateField()
    end_date = models.DateField()

    is_half_day = models.BooleanField(default=False)

    reason = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING"
    )

    applied_on = models.DateTimeField(auto_now_add=True)

    approved_by = models.ForeignKey(
        Employee,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_leaves"
    )

    approved_on = models.DateTimeField(null=True, blank=True)

    def total_days(self):
        if self.is_half_day:
            return 0.5
        return (self.end_date - self.start_date).days + 1

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

    def __str__(self):
        return f"{self.leave_request.id} - {self.action}"