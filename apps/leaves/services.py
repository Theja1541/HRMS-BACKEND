from datetime import timedelta
from apps.attendance.models import Attendance
from apps.payroll.utils import is_payroll_closed


def sync_leave_to_attendance(leave):
    """
    Sync approved leave to attendance records.
    Creates or updates attendance for each leave day.
    """

    current_date = leave.start_date

    while current_date <= leave.end_date:

        # Skip payroll locked months (safety)
        if is_payroll_closed(current_date.year, current_date.month):
            current_date += timedelta(days=1)
            continue

        attendance, created = Attendance.objects.get_or_create(
            employee=leave.employee,
            date=current_date
        )

        if leave.leave_type.is_paid:
            attendance.status = "PAID_LEAVE"
        else:
            attendance.status = "UNPAID_LEAVE"

        attendance.save()

        current_date += timedelta(days=1)