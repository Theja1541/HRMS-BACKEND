from rest_framework import serializers
from .models import Asset, AssetReturnRequest

class AssetSerializer(serializers.ModelSerializer):
    """Serializer for the unified Asset model."""
    class Meta:
        model = Asset
        fields = '__all__'

class AssetReturnRequestSerializer(serializers.ModelSerializer):
    """Serializer for AssetReturnRequest model"""
    class Meta:
        model = AssetReturnRequest
        fields = '__all__'
        read_only_fields = ('request_date', 'approved_by', 'approval_date')

class AssetReturnRequestCreateSerializer(serializers.ModelSerializer):
    """Serializer used when creating a return request; sets employee from request user"""
    class Meta:
        model = AssetReturnRequest
        fields = ('asset', 'admin_remarks')

    def create(self, validated_data):
        request = self.context.get('request')
        employee = getattr(request.user, 'employee_profile', None)
        if not employee:
            raise serializers.ValidationError('Employee profile not found')
        validated_data['employee'] = employee
        return super().create(validated_data)
