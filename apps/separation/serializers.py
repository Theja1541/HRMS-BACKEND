from rest_framework import serializers
from .models import ResignationRequest, FinalSettlement, FinalSettlementDeduction
from rest_framework.exceptions import ValidationError

class ResignationRequestSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    department = serializers.CharField(source='employee.department', read_only=True)
    designation = serializers.CharField(source='employee.designation', read_only=True)

    class Meta:
        model = ResignationRequest
        fields = '__all__'
        read_only_fields = ('company', 'employee', 'status', 'last_working_day', 'submitted_on')


try:
    from antigravity.serializers import BaseModelSerializer
except ImportError:
    # fallback in case it's not installed in the local environment
    class BaseModelSerializer(serializers.ModelSerializer):
        pass

class FinalSettlementDeductionSerializer(BaseModelSerializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, coerce_to_string=True)

    class Meta:
        model = FinalSettlementDeduction
        fields = ('id', 'deduction_type', 'description', 'amount', 'asset_return_id')

class FFSettlementSerializer(BaseModelSerializer):
    total_earnings = serializers.DecimalField(max_digits=12, decimal_places=2, coerce_to_string=True)
    total_deductions = serializers.DecimalField(max_digits=12, decimal_places=2, coerce_to_string=True)
    net_amount = serializers.DecimalField(max_digits=12, decimal_places=2, coerce_to_string=True)
    
    notice_period_shortfall_days = serializers.IntegerField(read_only=True)
    notice_shortfall_snapshot = serializers.JSONField(read_only=True)
    deductions = FinalSettlementDeductionSerializer(many=True, read_only=True)

    class Meta:
        model = FinalSettlement
        # As per the prompt: fields: id, resignation_request_id, total_earnings, total_deductions, net_amount, status, earnings_payload, locked, notice_period_shortfall_days, notice_shortfall_snapshot, deductions, created_at, updated_at
        fields = (
            'id', 'resignation_request_id', 'total_earnings', 'total_deductions', 'net_amount',
            'status', 'earnings_payload', 'locked', 'notice_period_shortfall_days',
            'notice_shortfall_snapshot', 'deductions', 'created_at', 'updated_at'
        )
        
    # Property fallback just in case model uses 'resignation' instead of 'resignation_request'
    resignation_request_id = serializers.IntegerField(source='resignation.id', read_only=True)

class FinalSettlementSerializer(serializers.ModelSerializer):
    deductions = FinalSettlementDeductionSerializer(many=True, read_only=True)
    approved_by_name = serializers.SerializerMethodField()
    resignation_details = ResignationRequestSerializer(source='resignation', read_only=True)

    class Meta:
        model = FinalSettlement
        fields = '__all__'
        read_only_fields = ('resignation',)

    def get_approved_by_name(self, obj):
        if obj.approved_by:
            return getattr(obj.approved_by, 'get_full_name', lambda: obj.approved_by.username)()
        return None

    def update(self, instance, validated_data):
        if instance.locked:
            raise ValidationError('Settlement is locked and cannot be modified.')
        return super().update(instance, validated_data)
