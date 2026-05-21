from datetime import date
from decimal import Decimal, ROUND_HALF_UP


TWOPLACES = Decimal("0.01")

PAYROLL_EARNING_FIELDS = (
    "basic",
    "da",
    "hra",
    "conveyance",
    "medical",
    "special_allowance",
)

PAYROLL_DEDUCTION_FIELDS = (
    "employee_pf",
    "professional_tax",
    "employee_esi",
    "tds",
    "medical_insurance",
)

PAYROLL_EMPLOYER_CONTRIBUTION_FIELDS = (
    "employer_pf",
    "employer_esi",
    "gratuity",
)

PAYROLL_COMPONENT_FIELDS = (
    PAYROLL_EARNING_FIELDS
    + PAYROLL_DEDUCTION_FIELDS
    + PAYROLL_EMPLOYER_CONTRIBUTION_FIELDS
)

PAYROLL_CALCULATED_FIELDS = (
    "gross_salary",
    "total_deductions",
    "net_salary",
    "additional_benefits",
    "ctc",
)


def _get_value(source, field_name):
    if hasattr(source, "get"):
        return source.get(field_name, 0)
    return getattr(source, field_name, 0)


def to_decimal(value):
    if value in (None, "", "null"):
        return Decimal("0.00")
    return Decimal(str(value))


def money(value):
    return to_decimal(value).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def normalize_salary_data(salary_data=None):
    salary_data = salary_data or {}
    return {
        field_name: money(_get_value(salary_data, field_name))
        for field_name in PAYROLL_COMPONENT_FIELDS
    }


def calculate_payroll(salary_data=None):
    components = normalize_salary_data(salary_data)

    gross_salary = money(
        sum((components[field] for field in PAYROLL_EARNING_FIELDS), Decimal("0.00"))
    )
    total_deductions = money(
        sum((components[field] for field in PAYROLL_DEDUCTION_FIELDS), Decimal("0.00"))
    )
    net_salary = money(gross_salary - total_deductions)
    additional_benefits = money(
        sum(
            (components[field] for field in PAYROLL_EMPLOYER_CONTRIBUTION_FIELDS),
            Decimal("0.00"),
        )
    )
    ctc = money(gross_salary + additional_benefits)

    return {
        "gross_salary": gross_salary,
        "total_deductions": total_deductions,
        "net_salary": net_salary,
        "additional_benefits": additional_benefits,
        "ctc": ctc,
    }


def build_salary_record(salary_data=None):
    components = normalize_salary_data(salary_data)
    return {
        **components,
        **calculate_payroll(components),
    }


class PayrollService:

    @staticmethod
    def generate_and_store(employee, year, month):
        from apps.attendance.services import AttendanceService

        from ..calculator import PayrollCalculator
        from ..models import PayrollMonth, Payslip

        payroll_month = PayrollMonth.objects.filter(
            year=year,
            month=month,
        ).first()

        if payroll_month and payroll_month.status == "CLOSED":
            raise Exception("Payroll month is closed. Cannot regenerate payroll.")

        attendance_data = AttendanceService.get_monthly_attendance(
            employee=employee,
            year=year,
            month=month,
        )
        summary = attendance_data["summary"]

        if summary.get("deductible_days") is None:
            raise Exception("Attendance summary invalid")

        payroll_data = PayrollCalculator.calculate(
            employee=employee,
            attendance_summary=summary,
        )

        payslip, _ = Payslip.objects.update_or_create(
            employee=employee,
            month=date(year, month, 1),
            defaults={
                "gross_salary": payroll_data["earnings"]["gross_salary"],
                "lop_deduction": payroll_data["earnings"]["lop_deduction"],
                "employee_pf": payroll_data["deductions"]["employee_pf"],
                "employer_pf": payroll_data["deductions"]["employer_pf"],
                "employee_esi": payroll_data["deductions"]["employee_esi"],
                "employer_esi": payroll_data["deductions"]["employer_esi"],
                "professional_tax": payroll_data["deductions"]["professional_tax"],
                "lop_days": payroll_data["deductions"]["lop_days"],
                "fixed_deductions": payroll_data["deductions"]["fixed_deductions"],
                "net_pay": payroll_data["net_salary"],
            },
        )

        return payslip