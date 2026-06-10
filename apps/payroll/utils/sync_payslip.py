from decimal import Decimal
from apps.payroll.models import Payslip, Salary
from apps.payroll.services.lop_service import calculate_lop_for_month
from apps.payroll.utils.payroll_calculations import calculate_payslip_totals

def sync_attendance_with_payslip(employee, year, month):
    """
    Recalculates LOP and updates the Payslip if it exists and is NOT PAID.
    Called whenever attendance is updated.
    """
    payslip = Payslip.objects.filter(employee=employee, month__year=year, month__month=month).first()
    
    if not payslip or payslip.status != "NOT PAID":
        return False
        
    salary = Salary.objects.filter(employee=employee).first()
    if not salary:
        return False
        
    # Recalculate LOP
    lop_days = calculate_lop_for_month(employee, year, month)
    
    # Recalculate totals
    totals = calculate_payslip_totals(
        salary_obj=salary,
        year=year,
        month=month,
        lop_days=lop_days
    )
    
    # Update payslip
    payslip.basic = totals['basic']
    payslip.da = totals['da']
    payslip.hra = totals['hra']
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
    payslip.tds_amount = totals.get('tds', Decimal('0'))
    payslip.fixed_deductions = totals.get('base_deductions', Decimal('0'))
    
    payslip.net_pay = totals['net_pay']
    
    payslip.save()
    
    return True
