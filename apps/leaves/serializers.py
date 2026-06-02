# apps/leaves/serializers.py

from rest_framework import serializers
from .models import LeaveRequest, LeaveBalance, LeaveType


# ======================================================
# LEAVE TYPE SERIALIZER
# ======================================================

class LeaveTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveType
        fields = "__all__"
        
    def validate(self, data):
        # 1. Carry Forward Validation
        carry_forward = data.get('carry_forward', getattr(self.instance, 'carry_forward', False))
        max_carry_forward = data.get('max_carry_forward', getattr(self.instance, 'max_carry_forward', 0))
        
        if not carry_forward and max_carry_forward > 0:
            raise serializers.ValidationError({
                "max_carry_forward": "Max carry forward must be 0 if carry forward is disabled."
            })
            
        # 2. Document Rules Validation
        document_required = data.get('document_required', getattr(self.instance, 'document_required', False))
        doc_days = data.get('document_required_after_days', getattr(self.instance, 'document_required_after_days', 0))
        
        if not document_required and doc_days > 0:
            data['document_required_after_days'] = 0 # auto correct
            
        # 3. Positive Integer Validations
        max_consecutive_days = data.get('max_consecutive_days', getattr(self.instance, 'max_consecutive_days', None))
        if max_consecutive_days is not None and max_consecutive_days <= 0:
             raise serializers.ValidationError({
                "max_consecutive_days": "Max consecutive days must be greater than 0."
             })
             
        # Unique code per company validation is typically handled by UniqueConstraint 
        # But we can also check it explicitly here if company is in data or context
        company = data.get('company', getattr(self.instance, 'company', None))
        code = data.get('code', getattr(self.instance, 'code', None))
        
        if company and code:
            qs = LeaveType.objects.filter(company=company, code=code)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError({
                    "code": f"Leave code '{code}' already exists for this company."
                })

        return data


# ======================================================
# LEAVE BALANCE SERIALIZER
# ======================================================

class LeaveBalanceSerializer(serializers.ModelSerializer):
    leave_type_name = serializers.CharField(
        source="leave_type.name",
        read_only=True
    )
    remaining = serializers.FloatField(read_only=True)

    class Meta:
        model = LeaveBalance
        fields = [
            "id",
            "year",
            "leave_type",
            "leave_type_name",
            "total_allocated",
            "used",
            "remaining"
        ]


# ======================================================
# LEAVE REQUEST SERIALIZER
# ======================================================

class LeaveRequestSerializer(serializers.ModelSerializer):

    employee_name = serializers.SerializerMethodField()

    leave_type_name = serializers.CharField(
        source="leave_type.name",
        read_only=True
    )

    total_days = serializers.SerializerMethodField()
    days = serializers.SerializerMethodField()

    class Meta:
        model = LeaveRequest
        fields = "__all__"

    def get_employee_name(self, obj):
        return f"{obj.employee.first_name} {obj.employee.last_name}".strip()

    def get_total_days(self, obj):
        return obj.total_days()
    
    def get_days(self, obj):
        return float(obj.total_days())