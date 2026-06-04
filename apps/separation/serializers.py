from rest_framework import serializers
from .models import ResignationRequest, FinalSettlement

class ResignationRequestSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    department = serializers.CharField(source='employee.department', read_only=True)
    designation = serializers.CharField(source='employee.designation', read_only=True)

    class Meta:
        model = ResignationRequest
        fields = '__all__'
        read_only_fields = ('company', 'employee', 'status', 'last_working_day', 'submitted_on')


class FinalSettlementSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinalSettlement
        fields = '__all__'
        read_only_fields = ('resignation',)
