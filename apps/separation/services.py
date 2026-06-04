from decimal import Decimal
from apps.assets.models import Asset
from apps.payroll.models import PayrollRecord # Assuming something like this exists
from .models import FinalSettlement, ResignationRequest

def calculate_final_settlement(resignation: ResignationRequest):
    """
    Calculates the final settlement for an employee including pending salary,
    leave encashment, and deductions for unreturned assets.
    """
    employee = resignation.employee
    
    # Earnings
    pending_salary = Decimal("0.00") # Would integrate with Payroll
    leave_encashment = Decimal("0.00") # Would integrate with Leaves
    bonus = Decimal("0.00")
    
    total_earnings = pending_salary + leave_encashment + bonus
    
    # Deductions
    notice_pay_recovery = Decimal("0.00")
    
    # Asset Deductions
    asset_damage_recovery = Decimal("0.00")
    
    # Query assigned assets that are damaged or missing during clearance
    # Assuming Asset model has 'status' and 'value' fields
    # unreturned_assets = Asset.objects.filter(employee=employee, status__in=['LOST', 'DAMAGED'])
    # for asset in unreturned_assets:
    #     asset_damage_recovery += asset.current_value if hasattr(asset, 'current_value') else Decimal("0.00")

    loan_recovery = Decimal("0.00")
    other_deductions = Decimal("0.00")
    
    total_deductions = notice_pay_recovery + asset_damage_recovery + loan_recovery + other_deductions
    net_amount = total_earnings - total_deductions

    # Create or update Final Settlement
    settlement, created = FinalSettlement.objects.get_or_create(
        resignation=resignation,
        defaults={
            'status': 'DRAFT'
        }
    )
    
    settlement.earnings_payload = {
        'pending_salary': str(pending_salary),
        'leave_encashment': str(leave_encashment),
        'bonus': str(bonus),
    }
    settlement.deductions_payload = {
        'notice_pay_recovery': str(notice_pay_recovery),
        'asset_damage_recovery': str(asset_damage_recovery),
        'loan_recovery': str(loan_recovery),
        'other_deductions': str(other_deductions),
    }
    
    settlement.total_earnings = total_earnings
    settlement.total_deductions = total_deductions
    settlement.net_amount = net_amount
    settlement.save()
    
    return settlement
