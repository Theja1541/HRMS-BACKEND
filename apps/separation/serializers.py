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


class FinalSettlementDeductionSerializer(serializers.ModelSerializer):
    deduction_type_display = serializers.CharField(source='get_deduction_type_display', read_only=True)

    class Meta:
        model = FinalSettlementDeduction
        fields = ('id', 'deduction_type', 'deduction_type_display', 'asset_return_id', 'description', 'amount')


class FinalSettlementSerializer(serializers.ModelSerializer):
    deductions = FinalSettlementDeductionSerializer(many=True, read_only=True)
    approved_by_name = serializers.SerializerMethodField()

    class Meta:
        model = FinalSettlement
        fields = '__all__'
        read_only_fields = ('resignation',)

    def get_approved_by_name(self, obj):
        if obj.approved_by:
            # Assumes User model has get_full_name() or similar, fallback to username
            return getattr(obj.approved_by, 'get_full_name', lambda: obj.approved_by.username)()
        return None

    def update(self, instance, validated_data):
        if instance.locked:
            raise ValidationError('Settlement is locked and cannot be modified.')
        return super().update(instance, validated_data)
