from calendar import monthrange
from decimal import Decimal

from ..services.payroll_service import build_salary_record, money, to_decimal


def calculate_salary_totals(salary_obj):
    return build_salary_record(salary_obj)


def calculate_payslip_totals(salary_obj, year, month, lop_days=0):
    totals = calculate_salary_totals(salary_obj)
    lop_days_decimal = to_decimal(lop_days)

    gross_salary = totals["gross_salary"]
    total_days = Decimal(str(monthrange(year, month)[1]))
    lop_deduction = Decimal("0.00")
    if total_days > 0 and lop_days_decimal > 0:
        lop_deduction = (gross_salary / total_days) * lop_days_decimal

    base_deductions = totals["total_deductions"]
    total_deductions_with_lop = base_deductions + lop_deduction
    net_pay = gross_salary - total_deductions_with_lop
    if net_pay < 0:
        net_pay = Decimal("0.00")

    return {
        **totals,
        "lop_days": money(lop_days_decimal),
        "lop_deduction": money(lop_deduction),
        "base_deductions": money(base_deductions),
        "total_deductions": money(total_deductions_with_lop),
        "net_pay": money(net_pay),
    }
