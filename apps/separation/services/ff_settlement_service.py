import datetime
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.core.exceptions import ValidationError
from ..models import ResignationRequest, FinalSettlement, FinalSettlementDeduction

WORKING_DAYS_PER_MONTH = Decimal("26")
SHORTFALL_EXEMPT_TYPES = {"TERMINATION", "RETIREMENT"}

class FFSettlementService:

    @staticmethod
    def calculate_notice_period_shortfall(resignation_request) -> dict:
        if getattr(resignation_request, 'resignation_date', None) is None or getattr(resignation_request, 'last_working_day', None) is None:
            return {"shortfall_days": 0, "deduction_amount": "0.00", "applied": False}
            
        actual_notice_given = (resignation_request.last_working_day - resignation_request.resignation_date).days
        contractual_notice = resignation_request.notice_period_days
        shortfall_days = max(0, contractual_notice - actual_notice_given)
        
        if shortfall_days == 0:
            return {"shortfall_days": 0, "deduction_amount": "0.00", "applied": False}
            
        daily_rate = resignation_request.employee.gross_salary / WORKING_DAYS_PER_MONTH
        deduction_amount = (daily_rate * Decimal(shortfall_days)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        
        return {
            "shortfall_days": shortfall_days,
            "contractual_notice_days": contractual_notice,
            "actual_notice_given_days": actual_notice_given,
            "daily_rate": str(daily_rate.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            "deduction_amount": str(deduction_amount),
            "applied": True
        }

    @staticmethod
    def generate_ff_settlement(resignation_request_id, created_by_user) -> FinalSettlement:
        with transaction.atomic():
            try:
                resignation_request = ResignationRequest.objects.select_related("employee").get(id=resignation_request_id)
            except ResignationRequest.DoesNotExist:
                raise ValidationError("Resignation request not found.")
                
            # Check Idempotency. Assume field could be named resignation or resignation_request
            if FinalSettlement.objects.filter(resignation_request=resignation_request).exists():
                raise ValidationError("F&F Settlement already exists for this resignation request. Use the update endpoint to modify deductions.")
                
            if resignation_request.status != "CLEARANCE_PENDING":
                raise ValidationError(f"Cannot generate settlement. Actual status is: {resignation_request.status}")
                
            if resignation_request.separation_type in SHORTFALL_EXEMPT_TYPES:
                snapshot = {}
                shortfall_days = 0
            else:
                snapshot = FFSettlementService.calculate_notice_period_shortfall(resignation_request)
                shortfall_days = snapshot.get("shortfall_days", 0)
                
            settlement = FinalSettlement.objects.create(
                resignation_request=resignation_request,
                total_earnings=Decimal("0.00"),
                total_deductions=Decimal("0.00"),
                net_amount=Decimal("0.00"),
                status="DRAFT",
                notice_period_shortfall_days=shortfall_days,
                notice_shortfall_snapshot=snapshot
            )
            
            if snapshot and snapshot.get("applied") is True:
                FinalSettlementDeduction.objects.create(
                    settlement=settlement,
                    deduction_type="NOTICE_PERIOD_SHORTFALL",
                    description=f"Notice period shortfall: {shortfall_days} day(s) deducted "
                                f"({snapshot['contractual_notice_days']} days required, "
                                f"{snapshot['actual_notice_given_days']} days served).",
                    amount=Decimal(snapshot["deduction_amount"])
                )
                
            all_deductions = sum((d.amount for d in settlement.deductions.all()), Decimal("0.00"))
            
            settlement.total_deductions = all_deductions.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            settlement.net_amount = (settlement.total_earnings - settlement.total_deductions).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            settlement.save(update_fields=["total_deductions", "net_amount"])
            
            return settlement
