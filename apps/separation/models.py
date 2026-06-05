from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError

# ============================================================
# TRANSACTIONAL MODELS
# ============================================================

class ResignationRequest(models.Model):
    SEPARATION_TYPES = (
        ('RESIGNATION', 'Resignation'),
        ('TERMINATION', 'Termination'),
        ('RETIREMENT', 'Retirement'),
        ('CONTRACT_END', 'Contract End'),
        ('ABSCONDING', 'Absconding'),
    )

    STATUS_CHOICES = (
        ('DRAFT', 'Draft'),
        ('SUBMITTED', 'Submitted'),
        ('MANAGER_APPROVED', 'Manager Approved'),
        ('HR_APPROVED', 'HR Approved'),
        ('CLEARANCE_PENDING', 'Clearance Pending'),
        ('SETTLEMENT_PENDING', 'Settlement Pending'),
        ('READY_FOR_RELIEVING', 'Ready For Relieving'),
        ('RELIEVED', 'Relieved'),
        ('REJECTED', 'Rejected'),
    )

    company = models.ForeignKey('accounts.Company', on_delete=models.CASCADE, related_name='resignations')
    employee = models.ForeignKey('employees.Employee', on_delete=models.CASCADE, related_name='resignations')
    separation_type = models.CharField(max_length=50, choices=SEPARATION_TYPES, default='RESIGNATION')
    
    reason = models.CharField(max_length=255)
    detailed_explanation = models.TextField(blank=True)
    
    submitted_on = models.DateTimeField(null=True, blank=True)
    notice_period_days = models.PositiveIntegerField(default=0)
    last_working_day = models.DateField(null=True, blank=True)
    
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='DRAFT')
    
    # JSON Fields for dynamic/workflow data
    approval_history = models.JSONField(default=list, blank=True, help_text="Stores approval roles, actions, and remarks")
    timeline = models.JSONField(default=list, blank=True, help_text="Stores timestamped events for tracking")
    clearance_data = models.JSONField(default=dict, blank=True, help_text="Stores department-wise clearance status")
    exit_interview = models.JSONField(default=dict, blank=True, help_text="Stores exit interview feedback and ratings")
    documents = models.JSONField(default=dict, blank=True, help_text="Stores paths to generated separation documents")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['company', 'status']),
            models.Index(fields=['employee']),
        ]

    def __str__(self):
        return f"{self.employee} - {self.status}"


class FinalSettlement(models.Model):
    STATUS_CHOICES = (
        ('DRAFT', 'Draft'),
        ('PENDING_APPROVAL', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('DISBURSED', 'Disbursed'),
        ('DISPUTED', 'Disputed'),
    )

    resignation = models.OneToOneField(ResignationRequest, on_delete=models.CASCADE, related_name='final_settlement')
    
    # Earnings & Deductions Details
    earnings_payload = models.JSONField(default=dict, blank=True)
    
    # Aggregate Totals
    total_earnings = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    net_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='DRAFT')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_settlements')
    approved_at = models.DateTimeField(null=True, blank=True)
    disbursed_at = models.DateTimeField(null=True, blank=True)
    locked = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Final Settlement for {self.resignation.employee}"

    def save(self, *args, **kwargs):
        if self.pk:
            orig = FinalSettlement.objects.get(pk=self.pk)
            if orig.locked:
                # Check if financial fields changed
                if (orig.total_earnings != self.total_earnings or
                    orig.total_deductions != self.total_deductions or
                    orig.net_amount != self.net_amount or
                    orig.earnings_payload != self.earnings_payload):
                    raise ValidationError("Cannot modify financial fields of a locked settlement.")
        super().save(*args, **kwargs)


class FinalSettlementDeduction(models.Model):
    DEDUCTION_TYPES = (
        ('ASSET_DAMAGE', 'Asset Damage'),
        ('ASSET_LOST', 'Asset Lost'),
        ('LOAN', 'Loan'),
        ('ADVANCE', 'Advance'),
        ('OTHER', 'Other'),
    )
    settlement = models.ForeignKey(FinalSettlement, on_delete=models.CASCADE, related_name='deductions')
    deduction_type = models.CharField(max_length=50, choices=DEDUCTION_TYPES)
    asset_return = models.ForeignKey('assets.AssetReturn', null=True, blank=True, on_delete=models.SET_NULL)
    description = models.TextField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.get_deduction_type_display()} - {self.amount}"
