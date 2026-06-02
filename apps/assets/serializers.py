from rest_framework import serializers
from .models import AssetCategory, Asset, AssetAssignment, AssetReturn, AssetMaintenance, AssetHistory
from apps.employees.serializers import EmployeeListSerializer
from django.contrib.auth import get_user_model

User = get_user_model()


class UserMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name']


class AssetCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetCategory
        fields = "__all__"
        read_only_fields = ['company', 'created_at', 'updated_at']


class AssetSerializer(serializers.ModelSerializer):
    category_details = AssetCategorySerializer(source="category", read_only=True)
    created_by_details = UserMinimalSerializer(source="created_by", read_only=True)
    
    class Meta:
        model = Asset
        fields = "__all__"
        read_only_fields = ['asset_code', 'company', 'created_at', 'updated_at']


class AssetAssignmentSerializer(serializers.ModelSerializer):
    asset_details = AssetSerializer(source="asset", read_only=True)
    employee_details = EmployeeListSerializer(source="employee", read_only=True)
    assigned_by_details = UserMinimalSerializer(source="assigned_by", read_only=True)

    class Meta:
        model = AssetAssignment
        fields = "__all__"
        read_only_fields = ['company', 'created_at', 'updated_at']


class AssetReturnSerializer(serializers.ModelSerializer):
    assignment_details = AssetAssignmentSerializer(source="assignment", read_only=True)
    returned_by_details = EmployeeListSerializer(source="returned_by", read_only=True)

    class Meta:
        model = AssetReturn
        fields = "__all__"
        read_only_fields = ['company', 'created_at']


class AssetMaintenanceSerializer(serializers.ModelSerializer):
    asset_details = AssetSerializer(source="asset", read_only=True)
    created_by_details = UserMinimalSerializer(source="created_by", read_only=True)

    class Meta:
        model = AssetMaintenance
        fields = "__all__"
        read_only_fields = ['company', 'created_at']


class AssetHistorySerializer(serializers.ModelSerializer):
    asset_details = AssetSerializer(source="asset", read_only=True)
    employee_details = EmployeeListSerializer(source="employee", read_only=True)
    performed_by_details = UserMinimalSerializer(source="performed_by", read_only=True)

    class Meta:
        model = AssetHistory
        fields = "__all__"
        read_only_fields = ['company', 'action_date']


class AssetRequestSerializer(serializers.ModelSerializer):
    asset_details = AssetSerializer(source="asset", read_only=True)
    employee_details = EmployeeListSerializer(source="employee", read_only=True)
    approved_by_details = UserMinimalSerializer(source="approved_by", read_only=True)

    class Meta:
        from .models import AssetRequest
        model = AssetRequest
        fields = "__all__"
        read_only_fields = ['company', 'request_date', 'approval_date', 'approved_by']


class AssetRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        from .models import AssetRequest
        model = AssetRequest
        fields = ['asset', 'request_type', 'employee_remarks']
