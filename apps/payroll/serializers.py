from rest_framework import serializers
from .models import Salary, Payslip
from .models import SalaryRevision

class SalarySerializer(serializers.ModelSerializer):

    yearly_ctc = serializers.SerializerMethodField()
    yearly_gross = serializers.SerializerMethodField()
    yearly_net = serializers.SerializerMethodField()

    class Meta:
        model = Salary
        fields = "__all__"

    def get_yearly_ctc(self, obj):
        return obj.ctc * 12

    def get_yearly_gross(self, obj):
        return obj.gross_salary * 12

    def get_yearly_net(self, obj):
        return obj.net_salary * 12

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


class SalaryRevisionSerializer(serializers.ModelSerializer):

    class Meta:
        model = SalaryRevision
        fields = "__all__"