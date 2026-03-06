from datetime import timedelta
from apps.attendance.models import Attendance, Holiday


def sync_leave_to_attendance(leave):

    current_date = leave.start_date

    while current_date <= leave.end_date:

        # Skip holidays
        if Holiday.objects.filter(date=current_date).exists():
            current_date += timedelta(days=1)
            continue

        # Determine attendance status
        if leave.is_half_day:
            status_value = "HALF_DAY"
        else:
            status_value = (
                "PAID_LEAVE"
                if leave.leave_type.is_paid
                else "UNPAID_LEAVE"
            )

        attendance, created = Attendance.objects.get_or_create(
            employee=leave.employee,
            date=current_date,
            defaults={
                "status": status_value,
                "source": "LEAVE_SYSTEM"
            }
        )

        if not created:
            if attendance.locked:
                raise Exception("Attendance is locked for payroll")

            attendance.status = status_value
            attendance.source = "LEAVE_SYSTEM"
            attendance.save(update_fields=["status", "source"])

        # For half-day, only one date should exist
        if leave.is_half_day:
            break

        current_date += timedelta(days=1)