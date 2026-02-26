from rest_framework import serializers
from .models import Salary, Payslip


class SalarySerializer(serializers.ModelSerializer):

    class Meta:
        model = Salary
        fields = "__all__"

    def validate_employee(self, value):
        if Salary.objects.filter(employee=value).exists():
            raise serializers.ValidationError(
                "Salary already set for this employee."
            )
        return value


class PayslipSerializer(serializers.ModelSerializer):

    employee_id = serializers.CharField(
        source="employee.employee_id",
        read_only=True
    )

    username = serializers.CharField(
        source="employee.user.username",
        read_only=True
    )

    class Meta:
        model = Payslip
        fields = [
            "id",
            "employee_id",
            "username",
            "month",

            # Salary structure
            "basic",
            "hra",
            "allowances",
            "gross_salary",

            # Attendance breakdown
            "working_days",
            "absent_days",
            "half_days",
            "late_days",
            "unpaid_leave_days",

            # Deductions
            "attendance_deduction",
            "late_penalty",
            "fixed_deductions",

            # Final
            "net_pay",
            "status",
            "generated_on",
            "paid_on",
        ]