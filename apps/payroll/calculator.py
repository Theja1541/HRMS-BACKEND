from decimal import Decimal
from calendar import monthrange


class PayrollCalculator:

    @staticmethod
    def calculate(employee, attendance_summary):

        salary = employee.salary

        # ========================
        # GROSS SALARY
        # ========================
        gross_salary = salary.gross_salary

        # ========================
        # ATTENDANCE (Already Calculated)
        # ========================
        lop_days = Decimal(attendance_summary.get("deductible_days", 0))

        year = attendance_summary.get("year")
        month = attendance_summary.get("month")

        total_days = Decimal(monthrange(year, month)[1])
        per_day_salary = gross_salary / total_days

        lop_deduction = per_day_salary * lop_days

        gross_after_lop = gross_salary - lop_deduction

        # ========================
        # PF
        # ========================
        employee_pf = Decimal("0.00")
        employer_pf = Decimal("0.00")

        if salary.pf_applicable:
            pf_base = salary.basic
            employee_pf = pf_base * Decimal("0.12")
            employer_pf = pf_base * Decimal("0.12")

        # ========================
        # ESI
        # ========================
        employee_esi = Decimal("0.00")
        employer_esi = Decimal("0.00")

        if salary.esi_applicable and gross_after_lop <= Decimal("21000"):
            employee_esi = gross_after_lop * Decimal("0.0075")
            employer_esi = gross_after_lop * Decimal("0.0325")

        # ========================
        # PROFESSIONAL TAX
        # ========================
        professional_tax = (
            Decimal("200") if gross_after_lop > Decimal("15000") else Decimal("0")
        )

        # ========================
        # NET PAY
        # ========================
        total_deductions = (
            employee_pf
            + employee_esi
            + professional_tax
            + salary.fixed_deductions
        )

        net_salary = gross_after_lop - total_deductions

        return {
            "earnings": {
                "gross_salary": gross_salary,
                "lop_deduction": lop_deduction,
            },
            "deductions": {
                "employee_pf": employee_pf,
                "employer_pf": employer_pf,
                "employee_esi": employee_esi,
                "employer_esi": employer_esi,
                "professional_tax": professional_tax,
                "lop_days": lop_days,
            },
            "net_salary": net_salary,
            "additional_benefits": {
                "ctc": gross_salary,
            },
            "ctc": gross_salary,
        }