from .models import Attendance
from .calculator import AttendanceCalculator


class AttendanceService:

    @staticmethod
    def get_monthly_attendance(user, year, month):
        """
        Fetches monthly attendance records
        and delegates calculation to AttendanceCalculator.
        """

        # Fetch monthly records
        records = Attendance.objects.filter(
            employee=user,
            date__year=year,
            date__month=month
        ).order_by("date")

        # Pure business logic calculation
        summary = AttendanceCalculator.calculate(
            records=records,
            year=year,
            month=month
        )

        return {
            "summary": summary,
            "records": records
        }