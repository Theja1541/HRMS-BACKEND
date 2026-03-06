from .models import PayrollRecord, PayrollMonth
from .calculator import PayrollCalculator
from apps.attendance.services import AttendanceService

class PayrollService:

    @staticmethod
    def generate_and_store(employee, year, month):

        # ==========================
        # 1️⃣ Check Payroll Lock
        # ==========================
        payroll_month = PayrollMonth.objects.filter(
            year=year,
            month=month
        ).first()

        if payroll_month and payroll_month.status == "CLOSED":
            raise Exception("Payroll month is closed. Cannot regenerate payroll.")

        # ==========================
        # 2️⃣ Get Attendance Summary
        # ==========================
        attendance_data = AttendanceService.get_monthly_attendance(
            employee=employee,
            year=year,
            month=month
        )

        summary = attendance_data["summary"]

        if summary.get("deductible_days") is None:
            raise Exception("Attendance summary invalid")

        # ==========================
        # 3️⃣ Calculate Payroll
        # ==========================
        payroll_data = PayrollCalculator.calculate(
            employee=employee,
            attendance_summary=summary
        )

        # ==========================
        # 4️⃣ Store in DB
        # ==========================
        record, created = PayrollRecord.objects.update_or_create(
            employee=employee,
            year=year,
            month=month,
            defaults={
                **payroll_data["earnings"],
                **payroll_data["deductions"],
                "net_salary": payroll_data["net_salary"],
                **payroll_data["additional_benefits"],
                "ctc": payroll_data["ctc"],
            }
        )

        return record