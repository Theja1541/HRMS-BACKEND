from decimal import Decimal
from datetime import timedelta
from apps.leaves.models import LeaveRequest
from apps.attendance.models import Attendance, Holiday


def calculate_lop_for_month(employee, year, month):

    # ==========================================
    # 1️⃣ Get all active holidays in month
    # ==========================================
    holidays = Holiday.objects.filter(
        date__year=year,
        date__month=month
    ).values_list("date", flat=True)

    holiday_set = set(holidays)

    total_lop_days = Decimal("0.0")

    # ==========================================
    # 2️⃣ Unpaid approved leave
    # ==========================================
    unpaid_leaves = LeaveRequest.objects.filter(
        employee=employee,
        status="APPROVED",
        leave_type__is_paid=False,
        start_date__year=year,
        start_date__month=month,
    )

    for leave in unpaid_leaves:

        current = leave.start_date

        while current <= leave.end_date:

            # Only count if same month
            if current.year == year and current.month == month:

                # ❌ Skip if holiday
                if current not in holiday_set:
                    total_lop_days += Decimal("1")

            current += timedelta(days=1)

    # ==========================================
    # 3️⃣ Absent attendance (exclude holidays)
    # ==========================================
    absents = Attendance.objects.filter(
        employee=employee,
        date__year=year,
        date__month=month,
        status="ABSENT"
    )

    for record in absents:
        if record.date not in holiday_set:
            total_lop_days += Decimal("1")

    return total_lop_days