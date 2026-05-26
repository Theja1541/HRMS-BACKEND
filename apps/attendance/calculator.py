from calendar import monthrange
from collections import defaultdict

from .constants import (
    STATUS_PRESENT,
    STATUS_HALF_DAY,
    STATUS_PAID_LEAVE,
    STATUS_UNPAID_LEAVE,
    STATUS_ABSENT,
    STATUS_HOLIDAY,
    STATUS_WEEK_OFF,
)
from apps.holidays.models import Holiday



class AttendanceCalculator:

    @staticmethod
    def calculate(records, year, month):
        """
        Pure business logic.
        Takes Attendance queryset or list.
        Returns structured monthly summary.
        """

        total_calendar_days = monthrange(year, month)[1]

        # Initialize counters safely
        summary_map = defaultdict(int)

        for record in records:
            summary_map[record.status] += 1

        present_days = summary_map[STATUS_PRESENT]
        half_days = summary_map[STATUS_HALF_DAY]
        paid_leave_days = summary_map[STATUS_PAID_LEAVE]
        unpaid_leave_days = summary_map[STATUS_UNPAID_LEAVE]
        absent_days = summary_map[STATUS_ABSENT]
        holiday_days = summary_map[STATUS_HOLIDAY]
        week_off_days = summary_map[STATUS_WEEK_OFF]

        # Working days exclude holidays & weekoffs
        working_days = (
            total_calendar_days
            - holiday_days
            - week_off_days
        )
        
        # Calculate Unpaid Holidays
        # Find which dates within this month are unpaid holidays
        unpaid_holiday_qs = Holiday.objects.filter(
            is_active=True,
            payment_type="UNPAID",
            from_date__year__lte=year,
            to_date__year__gte=year,
            from_date__month__lte=month,
            to_date__month__gte=month,
        )
        unpaid_holiday_dates = set()
        from datetime import timedelta
        for h in unpaid_holiday_qs:
            curr = h.from_date
            while curr <= (h.to_date or h.from_date):
                if curr.year == year and curr.month == month:
                    unpaid_holiday_dates.add(curr)
                curr += timedelta(days=1)
                
        # Count how many STATUS_HOLIDAY records fall on an unpaid holiday date
        unpaid_holiday_days = sum(
            1 for r in records if r.status == STATUS_HOLIDAY and r.date in unpaid_holiday_dates
        )

        # Payroll calculations
        payable_days = (
            present_days
            + (half_days * 0.5)
            + paid_leave_days
        )

        deductible_days = (
            unpaid_leave_days
            + absent_days
            + (half_days * 0.5)
            + unpaid_holiday_days
        )

        attendance_percentage = 0
        if working_days > 0:
            attendance_percentage = round(
                ((present_days + (half_days * 0.5)) / working_days) * 100,
                2
            )

        return {
            "total_calendar_days": total_calendar_days,
            "working_days": working_days,
            "present_days": present_days,
            "half_days": half_days,
            "paid_leave_days": paid_leave_days,
            "unpaid_leave_days": unpaid_leave_days,
            "absent_days": absent_days,
            "holiday_days": holiday_days,
            "week_off_days": week_off_days,
            "payable_days": payable_days,
            "deductible_days": deductible_days,
            "attendance_percentage": attendance_percentage,
        }