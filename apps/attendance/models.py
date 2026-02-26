from django.db import models
from django.utils import timezone
from datetime import timedelta
from apps.employees.models import Employee


class Attendance(models.Model):

    STATUS_CHOICES = [
        ("PRESENT", "Present"),
        ("ABSENT", "Absent"),
        ("HALF_DAY", "Half Day"),
        ("LATE", "Late"),
        ("PAID_LEAVE", "Paid Leave"),
        ("UNPAID_LEAVE", "Unpaid Leave"),
    ]

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="attendances"
    )

    date = models.DateField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PRESENT"
    )

    check_in = models.DateTimeField(null=True, blank=True)
    check_out = models.DateTimeField(null=True, blank=True)

    # Lock system
    marked_at = models.DateTimeField(auto_now_add=True)
    manually_unlocked = models.BooleanField(default=False)

    # 🔥 Payroll calculation helpers
    late_minutes = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ("employee", "date")
        ordering = ["-date"]
        indexes = [
            models.Index(fields=["date"]),
            models.Index(fields=["employee", "date"]),
        ]

    def is_locked(self):
        if self.manually_unlocked:
            return False

        if not self.marked_at:
            return False

        return timezone.now() >= self.marked_at + timedelta(hours=1)

    def is_deductible(self):
        """
        Returns True if salary deduction applies.
        Used by payroll engine.
        """
        return self.status in ["ABSENT", "UNPAID_LEAVE"]

    def is_half_day(self):
        return self.status == "HALF_DAY"

    def is_late(self):
        return self.status == "LATE"

    def __str__(self):
        return f"{self.employee.employee_id} - {self.date} - {self.status}"