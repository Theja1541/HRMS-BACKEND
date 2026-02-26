import calendar
from datetime import date
from decimal import Decimal
from apps.attendance.models import Attendance


def calculate_monthly_salary(employee, year, month):

    basic = employee.basic_salary
    allowances = employee.allowances
    fixed_deductions = employee.deductions

    gross_salary = basic + allowances

    # 1️⃣ Total days in month
    total_days_in_month = calendar.monthrange(year, month)[1]

    # 2️⃣ Calculate working days (exclude Sundays for now)
    working_days = 0

    for day in range(1, total_days_in_month + 1):
        current_date = date(year, month, day)

        # Sunday = 6
        if current_date.weekday() != 6:
            working_days += 1

    working_days = Decimal(working_days)

    # 3️⃣ Per day salary
    per_day_salary = gross_salary / working_days

    # 4️⃣ Get attendance
    records = Attendance.objects.filter(
        employee=employee,
        date__year=year,
        date__month=month
    )

    absent_days = 0
    unpaid_leave_days = 0
    half_days = 0
    late_days = 0

    for record in records:
        if record.status == "ABSENT":
            absent_days += 1
        elif record.status == "UNPAID_LEAVE":
            unpaid_leave_days += 1
        elif record.status == "HALF_DAY":
            half_days += 1
        elif record.status == "LATE":
            late_days += 1

    # 5️⃣ Deductions
    full_day_deduction = per_day_salary * Decimal(absent_days + unpaid_leave_days)
    half_day_deduction = per_day_salary * Decimal("0.5") * Decimal(half_days)

    late_penalty_per_day = Decimal("100")
    late_penalty = late_penalty_per_day * Decimal(late_days)

    attendance_deduction = full_day_deduction + half_day_deduction

    net_salary = gross_salary - attendance_deduction - late_penalty - fixed_deductions

    return {
        "gross_salary": gross_salary,
        "working_days": working_days,
        "per_day_salary": per_day_salary,
        "absent_days": absent_days,
        "unpaid_leave_days": unpaid_leave_days,
        "half_days": half_days,
        "late_days": late_days,
        "attendance_deduction": attendance_deduction,
        "late_penalty": late_penalty,
        "fixed_deductions": fixed_deductions,
        "net_salary": net_salary
    }