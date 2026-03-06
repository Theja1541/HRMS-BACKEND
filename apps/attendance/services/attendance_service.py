from decimal import Decimal
from calendar import monthrange
from django.db.models import Sum, Case, When, Value, DecimalField
from apps.attendance.models import Attendance
from apps.attendance.constants import (
    STATUS_ABSENT,
    STATUS_UNPAID_LEAVE,
    STATUS_HALF_DAY,
)


class AttendanceService:

    @staticmethod
    def get_monthly_attendance(employee, year, month):

        queryset = Attendance.objects.filter(
            employee=employee,
            date__year=year,
            date__month=month
        )

        # =========================
        # 🔥 Database-Level Deduction
        # =========================
        deduction_result = queryset.aggregate(
            deductible_days=Sum(
                Case(
                    When(status=STATUS_ABSENT, then=Value(1)),
                    When(status=STATUS_UNPAID_LEAVE, then=Value(1)),
                    When(status=STATUS_HALF_DAY, then=Value(Decimal("0.5"))),
                    default=Value(0),
                    output_field=DecimalField(max_digits=5, decimal_places=2)
                )
            )
        )

        deductible_days = deduction_result["deductible_days"] or Decimal("0.0")

        summary = {
            "year": year,
            "month": month,
            "total_days_in_month": monthrange(year, month)[1],
            "deductible_days": deductible_days,
        }

        return {
            "records": queryset,
            "summary": summary,
        }