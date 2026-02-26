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

    employee_name = serializers.CharField(
        source="employee.user.username",
        read_only=True
    )

    leave_type_name = serializers.CharField(
        source="leave_type.name",
        read_only=True
    )

    total_days = serializers.SerializerMethodField()

    class Meta:
        model = LeaveRequest
        fields = "__all__"

    def get_total_days(self, obj):
        return obj.total_days()