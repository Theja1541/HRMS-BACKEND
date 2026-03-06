# from django.db import models
# from django.utils import timezone
# from datetime import timedelta
# from .constants import ATTENDANCE_STATUS_CHOICES
# # from apps.employees.models import Employee


# # class Attendance(models.Model):

# #     STATUS_CHOICES = [
# #         ("PRESENT", "Present"),
# #         ("ABSENT", "Absent"),
# #         ("HALF_DAY", "Half Day"),
# #         ("LATE", "Late"),
# #         ("PAID_LEAVE", "Paid Leave"),
# #         ("UNPAID_LEAVE", "Unpaid Leave"),
# #         ("HOLIDAY", "Holiday"),
# #     ]

# #     employee = models.ForeignKey(
# #         Employee,
# #         on_delete=models.CASCADE,
# #         related_name="attendances"
# #     )

# #     date = models.DateField()

# #     status = models.CharField(
# #         max_length=20,
# #         choices=STATUS_CHOICES,
# #         default="PRESENT"
# #     )

# #     check_in = models.DateTimeField(null=True, blank=True)
# #     check_out = models.DateTimeField(null=True, blank=True)

# #     # Lock system
# #     marked_at = models.DateTimeField(auto_now_add=True)
# #     manually_unlocked = models.BooleanField(default=False)

# #     # 🔥 Payroll calculation helpers
# #     late_minutes = models.PositiveIntegerField(default=0)
# #     notes = models.TextField(blank=True, null=True)

# #     class Meta:
# #         unique_together = ("employee", "date")
# #         ordering = ["-date"]
# #         indexes = [
# #             models.Index(fields=["date"]),
# #             models.Index(fields=["employee", "date"]),
# #         ]

# #     def is_locked(self):
# #         if self.manually_unlocked:
# #             return False

# #         if not self.marked_at:
# #             return False

# #         return timezone.now() >= self.marked_at + timedelta(hours=1)

# #     def is_deductible(self):
# #         """
# #         Returns True if salary deduction applies.
# #         Used by payroll engine.
# #         """
# #         return self.status in ["ABSENT", "UNPAID_LEAVE"]

# #     def is_half_day(self):
# #         return self.status == "HALF_DAY"

# #     def is_late(self):
# #         return self.status == "LATE"

# #     def __str__(self):
# #         return f"{self.employee.employee_id} - {self.date} - {self.status}"
    

# class Holiday(models.Model):
#     name = models.CharField(max_length=255)
#     date = models.DateField(unique=True)
#     is_optional = models.BooleanField(default=False)

#     class Meta:
#         ordering = ["date"]

#     def __str__(self):
#         return f"{self.name} - {self.date}"


# class Attendance(models.Model):

#     status = models.CharField(
#     max_length=20,
#     choices=ATTENDANCE_STATUS_CHOICES,
# )
    
#     employee = models.ForeignKey(
#     "employees.Employee",
#     on_delete=models.CASCADE,
#     related_name="attendances"
# )

#     date = models.DateField()

#     status = models.CharField(
#         max_length=20,
#         choices=STATUS_CHOICES,
#     )

#     attendance_type = models.CharField(
#     max_length=20,
#     choices=[
#         ("OFFICE", "Office"),
#         ("WFH", "Work From Home"),
#         ("FIELD", "Field Work"),
#     ],
#     default="OFFICE"
# )

#     check_in = models.DateTimeField(null=True, blank=True)
#     check_out = models.DateTimeField(null=True, blank=True)

#     # Late handling
#     is_late = models.BooleanField(default=False)
#     late_minutes = models.PositiveIntegerField(default=0)

#     # Work hours
#     work_hours = models.DecimalField(
#         max_digits=5,
#         decimal_places=2,
#         null=True,
#         blank=True
#     )

#     # Lock system
#     locked = models.BooleanField(default=False)
#     locked_at = models.DateTimeField(null=True, blank=True)

#     notes = models.TextField(blank=True, null=True)

#     class Meta:
#         unique_together = ("employee", "date")
#         ordering = ["-date"]
#         indexes = [
#             models.Index(fields=["date"]),
#             models.Index(fields=["employee", "date"]),
#         ]



# class WorkCalendar(models.Model):
#     """
#     Defines working structure for a group of employees.
#     """

#     name = models.CharField(max_length=100)

#     # 0=Monday ... 6=Sunday
#     weekend_days = models.JSONField(default=list)

#     second_saturday_off = models.BooleanField(default=False)
#     fourth_saturday_off = models.BooleanField(default=False)

#     working_hours_per_day = models.DecimalField(max_digits=4, decimal_places=2, default=8.0)

#     is_active = models.BooleanField(default=True)

#     def __str__(self):
#         return self.name
    

# class Shift(models.Model):
#     """
#     Defines working shift timing.
#     """

#     name = models.CharField(max_length=100)

#     start_time = models.TimeField()
#     end_time = models.TimeField()

#     grace_minutes = models.IntegerField(default=15)

#     is_night_shift = models.BooleanField(default=False)

#     def __str__(self):
#         return self.name


from django.db import models
from django.utils import timezone
from datetime import timedelta
from .constants import (
    ATTENDANCE_STATUS_CHOICES,
    STATUS_ABSENT,
    STATUS_UNPAID_LEAVE,
    STATUS_HALF_DAY,
)


class Holiday(models.Model):
    name = models.CharField(max_length=255)
    date = models.DateField(unique=True)
    is_optional = models.BooleanField(default=False)

    class Meta:
        ordering = ["date"]

    def __str__(self):
        return f"{self.name} - {self.date}"


class Attendance(models.Model):

    STATUS_CHOICES = (
        ("PRESENT", "Present"),
        ("HALF_DAY", "Half Day"),
        ("PAID_LEAVE", "Paid Leave"),
        ("UNPAID_LEAVE", "Unpaid Leave"),
        ("ABSENT", "Absent"),
        ("HOLIDAY", "Holiday"),
        ("WEEK_OFF", "Week Off"),
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES
    )

    employee = models.ForeignKey(
        "employees.Employee",
        on_delete=models.CASCADE,
        related_name="attendances"
    )

    date = models.DateField()

    status = models.CharField(
        max_length=20,
        choices=ATTENDANCE_STATUS_CHOICES,
        default="PRESENT"
    )

    attendance_type = models.CharField(
        max_length=20,
        choices=[
            ("OFFICE", "Office"),
            ("WFH", "Work From Home"),
            ("FIELD", "Field Work"),
        ],
        default="OFFICE"
    )

    check_in = models.DateTimeField(null=True, blank=True)
    check_out = models.DateTimeField(null=True, blank=True)

    # Late handling
    is_late = models.BooleanField(default=False)
    late_minutes = models.PositiveIntegerField(default=0)

    # Work hours (calculated)
    work_hours = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True
    )

    # Lock system
    locked = models.BooleanField(default=False)
    locked_at = models.DateTimeField(null=True, blank=True)

    notes = models.TextField(blank=True, null=True)

    SOURCE_CHOICES = (
    ("MANUAL", "Manual"),
    ("LEAVE_SYSTEM", "Leave System"),
    ("AUTO_SYSTEM", "Auto System"),
    )
    
    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default="MANUAL")

    class Meta:
        unique_together = ("employee", "date")
        ordering = ["-date"]
        indexes = [
            models.Index(fields=["date"]),
            models.Index(fields=["employee", "date"]),
            models.Index(fields=["status"]),
        ]

    def lock(self):
        """Lock attendance record."""
        self.locked = True
        self.locked_at = timezone.now()
        self.save(update_fields=["locked", "locked_at"])

    def unlock(self):
        """Unlock attendance record."""
        self.locked = False
        self.locked_at = None
        self.save(update_fields=["locked", "locked_at"])

    def is_locked(self):
        return self.locked

    def is_deductible(self):
        """
        Returns True if salary deduction applies.
        Used by payroll engine.
        """
        return self.status in [
            STATUS_ABSENT,
            STATUS_UNPAID_LEAVE,
        ]

    def is_half_day(self):
        return self.status == STATUS_HALF_DAY


    def __str__(self):
        return f"{self.employee} - {self.date} - {self.status}"


class WorkCalendar(models.Model):
    """
    Defines working structure for a group of employees.
    """

    name = models.CharField(max_length=100)

    # 0=Monday ... 6=Sunday
    weekend_days = models.JSONField(default=list)

    second_saturday_off = models.BooleanField(default=False)
    fourth_saturday_off = models.BooleanField(default=False)

    working_hours_per_day = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=8.0
    )

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Shift(models.Model):
    """
    Defines working shift timing.
    """

    name = models.CharField(max_length=100)

    start_time = models.TimeField()
    end_time = models.TimeField()

    grace_minutes = models.IntegerField(default=15)

    is_night_shift = models.BooleanField(default=False)

    def __str__(self):
        return self.name