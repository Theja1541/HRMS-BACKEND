from rest_framework import serializers
from .models import Employee, EmployeeHistory


# ============================================================
# EMPLOYEE HISTORY SERIALIZER
# ============================================================

class EmployeeHistorySerializer(serializers.ModelSerializer):
    changed_by = serializers.StringRelatedField()

    class Meta:
        model = EmployeeHistory
        fields = [
            "field_name",
            "old_value",
            "new_value",
            "changed_at",
            "changed_by",
        ]


# ============================================================
# EMPLOYEE LIST SERIALIZER (Lightweight – For Table View)
# ============================================================

class EmployeeListSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = [
            "id",
            "employee_id",
            "full_name",
            "email",
            "mobile",
            "department",
            "status",
        ]

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name or ''}".strip()

    def get_status(self, obj):
        return "Active" if obj.is_active else "Inactive"


# ============================================================
# EMPLOYEE DETAIL SERIALIZER (Full Profile View)
# ============================================================

class EmployeeDetailSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    history = EmployeeHistorySerializer(many=True, read_only=True)

    class Meta:
        model = Employee
        fields = "__all__"

    # ------------------------------
    # Computed Fields
    # ------------------------------

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name or ''}".strip()

    def get_status(self, obj):
        return "Active" if obj.is_active else "Inactive"

    # ------------------------------
    # Validation (Manual Employee ID)
    # ------------------------------

    def validate_employee_id(self, value):
        if not value:
            raise serializers.ValidationError(
                "Employee ID is required."
            )

        # Check uniqueness manually (important for update)
        qs = Employee.objects.filter(employee_id=value)

        if self.instance:
            qs = qs.exclude(id=self.instance.id)

        if qs.exists():
            raise serializers.ValidationError(
                "Employee ID already exists."
            )

        return value

    def validate_email(self, value):
        qs = Employee.objects.filter(email=value)

        if self.instance:
            qs = qs.exclude(id=self.instance.id)

        if qs.exists():
            raise serializers.ValidationError(
                "Email already exists."
            )

        return value