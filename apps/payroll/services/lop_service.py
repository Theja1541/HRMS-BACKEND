from decimal import Decimal
from datetime import timedelta
from apps.leaves.models import LeaveRequest
from apps.attendance.models import Attendance
from apps.holidays.models import Holiday


def calculate_lop_for_month(employee, year, month):

    # ==========================================
    # 1️⃣ Get all active holidays in month
    # ==========================================
    holidays = Holiday.objects.filter(
        from_date__year__lte=year,
        to_date__year__gte=year,
        from_date__month__lte=month,
        to_date__month__gte=month,
        is_active=True
    )

    holiday_set = set()
    for h in holidays:
        current = h.from_date
        while current <= h.to_date:
            if current.year == year and current.month == month:
                holiday_set.add(current)
            current += timedelta(days=1)

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
    # 3️⃣ Absent and Unpaid Leave attendance (exclude holidays)
    # ==========================================
    absents = Attendance.objects.filter(
        employee=employee,
        date__year=year,
        date__month=month,
        status__in=["ABSENT", "UNPAID_LEAVE"]
    )

    for record in absents:
        if record.date not in holiday_set:
            total_lop_days += Decimal("1")
            
    # ==========================================
    # 4️⃣ Unpaid Holidays
    # ==========================================
    # Re-query the holiday set to find UNPAID holidays
    unpaid_holidays = holidays.filter(payment_type="UNPAID")
    for h in unpaid_holidays:
        current = h.from_date
        while current <= (h.to_date or h.from_date):
            if current.year == year and current.month == month:
                # If an employee has an attendance record for this unpaid holiday
                # (and it's not already counted as absent), we add LOP.
                # Actually, if it's an unpaid holiday, everyone gets LOP unless they worked.
                # Let's check if they were PRESENT_ON_HOLIDAY.
                att = Attendance.objects.filter(employee=employee, date=current).first()
                if not att or att.status != "PRESENT_ON_HOLIDAY":
                    total_lop_days += Decimal("1")
            current += timedelta(days=1)

    return total_lop_days