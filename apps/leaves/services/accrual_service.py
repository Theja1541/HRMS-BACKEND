from decimal import Decimal
from datetime import date
from django.db import transaction
from apps.leaves.models import LeaveType, LeaveBalance
from apps.employees.models import Employee


def credit_monthly_leaves():
    """
    Credit monthly accrued leaves to all active employees.
    Run this on 1st of every month via Celery Beat.
    """
    today = date.today()
    current_year = today.year
    current_month = today.month
    
    leave_types = LeaveType.objects.filter(
        accrual_type="MONTHLY",
        is_active=True
    )
    
    employees = Employee.objects.filter(is_active=True)
    
    credited_count = 0
    
    with transaction.atomic():
        for leave_type in leave_types:
            monthly_credit = leave_type.annual_quota / Decimal("12")
            
            for employee in employees:
                # Skip if joined after this month
                if employee.joining_date and employee.joining_date.year == current_year:
                    if employee.joining_date.month > current_month:
                        continue
                
                # Check if already credited
                balance, created = LeaveBalance.objects.get_or_create(
                    employee=employee,
                    leave_type=leave_type,
                    year=current_year,
                    defaults={"total_allocated": Decimal("0")}
                )
                
                # Check if balance already accounts for this month (simplified)
                # Without log, assume if total_allocated > (month-1)*monthly_credit, it's credited
                expected_balance = monthly_credit * (current_month - 1)
                if balance.total_allocated > expected_balance:
                    continue
                
                # Get or create balance
                balance, created = LeaveBalance.objects.get_or_create(
                    employee=employee,
                    leave_type=leave_type,
                    year=current_year,
                    defaults={"total_allocated": Decimal("0")}
                )
                
                # Credit leaves
                balance.total_allocated += monthly_credit
                balance.save()
                

                credited_count += 1
    
    return credited_count


def credit_annual_leaves():
    """
    Credit annual leaves to all active employees on Jan 1st.
    """
    today = date.today()
    current_year = today.year
    
    leave_types = LeaveType.objects.filter(
        accrual_type="ANNUAL",
        is_active=True
    )
    
    employees = Employee.objects.filter(is_active=True)
    
    credited_count = 0
    
    with transaction.atomic():
        for leave_type in leave_types:
            for employee in employees:
                # Skip if joined after this year
                if employee.joining_date and employee.joining_date.year > current_year:
                    continue
                
                # Check if already credited
                balance = LeaveBalance.objects.filter(
                    employee=employee,
                    leave_type=leave_type,
                    year=current_year
                ).first()
                
                if balance and balance.total_allocated > 0:
                    continue
                
                # Create or update balance
                balance, created = LeaveBalance.objects.get_or_create(
                    employee=employee,
                    leave_type=leave_type,
                    year=current_year,
                    defaults={"total_allocated": leave_type.annual_quota}
                )
                
                if not created and balance.total_allocated == 0:
                    balance.total_allocated = leave_type.annual_quota
                    balance.save()
                

                credited_count += 1
    
    return credited_count


def get_employee_accrual_history(employee, leave_type, year):
    """
    Get accrual history for an employee.
    """
    return []
