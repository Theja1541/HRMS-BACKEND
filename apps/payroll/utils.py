from calendar import monthrange
from decimal import Decimal
from apps.attendance.models import Attendance
from .models import PayrollMonth
from datetime import date


# ==========================================================
# PAYROLL MONTH LOCK CHECK
# ==========================================================

def is_payroll_closed(year, month):
    return PayrollMonth.objects.filter(
        year=year,
        month=month,
        status="CLOSED"
    ).exists()

# ==========================================================
# SUPER ADMIN CHECK
# ==========================================================

def is_super_admin(user):
    return (
        user.is_authenticated and
        hasattr(user, "role") and
        user.role == "SUPER_ADMIN"
    )


# ==========================================================
# ATTENDANCE SUMMARY
# ==========================================================

def get_attendance_summary(employee, year, month):

    total_days = monthrange(year, month)[1]

    records = Attendance.objects.filter(
        employee=employee,
        date__year=year,
        date__month=month
    )

    present_days = records.filter(status="PRESENT").count()
    leave_days = records.filter(status="LEAVE").count()
    absent_days = records.filter(status="ABSENT").count()

    return {
        "total_days": total_days,
        "present_days": present_days,
        "leave_days": leave_days,
        "absent_days": absent_days,
    }


# ==========================================================
# PAYABLE SALARY CALCULATION
# ==========================================================

def calculate_payable_salary(employee, salary, year, month):

    summary = get_attendance_summary(employee, year, month)

    total_days = summary["total_days"]
    present_days = summary["present_days"]
    leave_days = summary["leave_days"]

    paid_days = present_days + leave_days

    if total_days == 0:
        per_day_salary = Decimal("0.00")
        payable_salary = Decimal("0.00")
    else:
        gross_salary = salary.basic + salary.hra + salary.allowances
        per_day_salary = gross_salary / Decimal(total_days)
        payable_salary = per_day_salary * Decimal(paid_days)

    return {
        **summary,
        "paid_days": paid_days,
        "per_day_salary": per_day_salary.quantize(Decimal("0.01")),
        "payable_salary": payable_salary.quantize(Decimal("0.01")),
    }


def get_current_salary(employee):

    today = date.today()

    return (
        employee.salary_revisions
        .filter(effective_from__lte=today)
        .order_by("-effective_from")
        .first()
    )