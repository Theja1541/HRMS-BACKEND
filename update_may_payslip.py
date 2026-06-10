import os
import django
import sys
from decimal import Decimal
from datetime import date

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hrms_backend.settings')
django.setup()

from apps.employees.models import Employee
from apps.payroll.models import Payslip, Salary
from apps.payroll.utils.payroll_calculations import calculate_payslip_totals

# Get employee
employee = Employee.objects.filter(first_name__icontains='CHAITANYA', last_name__icontains='KANTAMNENI').first()
if not employee:
    print("Employee not found")
    sys.exit(1)

print(f"Found employee: {employee}")

year = 2026
month = 5
lop_days = Decimal('0')

salary = Salary.objects.filter(employee=employee).first()
if not salary:
    print("Salary not found for employee")
    sys.exit(1)

# Calculate totals with 6 LOP days
totals = calculate_payslip_totals(salary, year, month, lop_days)

print(f"Calculated totals: {totals}")

# Get or create payslip for May 2026
payslip, created = Payslip.objects.get_or_create(
    employee=employee,
    month=date(year, month, 1),
    defaults={'status': 'NOT PAID'}
)

# Update payslip values based on totals
payslip.basic = totals['basic']
payslip.hra = totals['hra']
payslip.da = totals['da']
payslip.conveyance = totals['conveyance']
payslip.medical = totals['medical']
payslip.special_allowance = totals['special_allowance']
payslip.medical_insurance = totals['medical_insurance']
payslip.gross_salary = totals['gross_salary']
payslip.lop_days = totals['lop_days']
payslip.lop_deduction = totals['lop_deduction']
payslip.employee_pf = totals['employee_pf']
payslip.employer_pf = totals['employer_pf']
payslip.employee_esi = totals['employee_esi']
payslip.employer_esi = totals['employer_esi']
payslip.professional_tax = totals['professional_tax']
payslip.tds_amount = totals.get('tds', 0)
payslip.fixed_deductions = totals.get('base_deductions', 0)
payslip.net_pay = totals['net_pay']

payslip.save()

print(f"Updated Payslip for {month}/{year}: LOP Days: {payslip.lop_days}, LOP Deduction: {payslip.lop_deduction}, Net Pay: {payslip.net_pay}")
