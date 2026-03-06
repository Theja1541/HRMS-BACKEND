from rest_framework import serializers
from .models import Employee, EmployeeHistory
from apps.payroll.models import Salary
from django.db import transaction
import json
from rest_framework import serializers
from django.db import transaction
from decimal import Decimal
from apps.payroll.serializers import SalarySerializer
from apps.payroll.serializers import SalaryRevisionSerializer


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
        fields = "__all__"
        

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

    # ❗ REMOVE read_only=True
    # salary = SalarySerializer(required=False)
    salary = SalarySerializer(read_only=True)

    salary_history = SalaryRevisionSerializer(
    source="salary_revisions",
    many=True,
    read_only=True
)

    class Meta:
        model = Employee
        fields = "__all__"

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name or ''}".strip()

    def get_status(self, obj):
        return "Active" if obj.is_active else "Inactive"


    # ================= CREATE =================

    @transaction.atomic
    def create(self, validated_data):

        salary_data = validated_data.pop("salary", None)

        if isinstance(salary_data, str):
            salary_data = json.loads(salary_data)

        employee = Employee.objects.create(**validated_data)

        if salary_data:
            from decimal import Decimal

            cleaned_salary = {
                k: Decimal(v) if v not in ["", None] else Decimal("0")
                for k, v in salary_data.items()
            }

            Salary.objects.create(employee=employee, **cleaned_salary)

        return employee


    # ================= UPDATE =================

    @transaction.atomic
    def update(self, instance, validated_data):

        request = self.context.get("request")

        salary_data = request.data.get("salary")

        if salary_data:
            salary_data = json.loads(salary_data)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        if salary_data:
            salary_obj, created = Salary.objects.get_or_create(employee=instance)

            for attr, value in salary_data.items():
                setattr(
                    salary_obj,
                    attr,
                    Decimal(value) if value not in ["", None] else Decimal("0")
                )

            salary_obj.save()

        return instance