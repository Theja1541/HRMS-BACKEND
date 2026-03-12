from rest_framework import serializers
from .models import CompanyAsset, AssetAssignment, AssetReturnRequest
from apps.employees.models import Employee


class CompanyAssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyAsset
        fields = '__all__'


class AssetAssignmentSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.first_name', read_only=True)
    asset_name = serializers.CharField(source='asset.asset_name', read_only=True)

    class Meta:
        model = AssetAssignment
        fields = '__all__'


class AssetReturnRequestSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    department = serializers.CharField(source='employee.department', read_only=True)
    approved_by_name = serializers.SerializerMethodField()

    class Meta:
        model = AssetReturnRequest
        fields = '__all__'
        read_only_fields = ('request_date', 'approved_by', 'approval_date')

    def get_employee_name(self, obj):
        if obj.employee:
            return f"{obj.employee.first_name} {obj.employee.last_name}"
        return "Unknown"

    def get_approved_by_name(self, obj):
        if obj.approved_by:
            return f"{obj.approved_by.first_name} {obj.approved_by.last_name}"
        return None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.employee and instance.employee.department:
            data['department'] = instance.employee.department
        else:
            data['department'] = 'N/A'
        return data


class AssetReturnRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetReturnRequest
        fields = ['asset_type', 'asset_name', 'serial_number', 'description', 'condition', 'return_date', 'comments']

    def create(self, validated_data):
        request = self.context.get('request')
        try:
            employee = request.user.employee_profile
        except Exception:
            raise serializers.ValidationError("Employee profile not found for this user")
        validated_data['employee'] = employee
        return super().create(validated_data)
