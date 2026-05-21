from decimal import Decimal

from rest_framework import serializers

from .models import Payslip, Salary, SalaryRevision
from .services.payroll_service import money


class EmployeeSalarySerializer(serializers.ModelSerializer):

    yearly_ctc = serializers.SerializerMethodField()
    yearly_gross = serializers.SerializerMethodField()
    yearly_net = serializers.SerializerMethodField()

    class Meta:
        model = Salary
        fields = [
            "id",
            "employee",
            "basic",
            "da",
            "hra",
            "conveyance",
            "medical",
            "special_allowance",
            "employee_pf",
            "professional_tax",
            "employee_esi",
            "tds",
            "medical_insurance",
            "employer_pf",
            "employer_esi",
            "gratuity",
            "gross_salary",
            "total_deductions",
            "net_salary",
            "additional_benefits",
            "ctc",
            "created_at",
            "updated_at",
            "yearly_ctc",
            "yearly_gross",
            "yearly_net",
        ]
        read_only_fields = [
            "gross_salary",
            "total_deductions",
            "net_salary",
            "additional_benefits",
            "ctc",
            "created_at",
            "updated_at",
            "yearly_ctc",
            "yearly_gross",
            "yearly_net",
        ]

    def _yearly_amount(self, value):
        return money(Decimal(value or 0) * Decimal("12"))

    def get_yearly_ctc(self, obj):
        return self._yearly_amount(obj.ctc)

    def get_yearly_gross(self, obj):
        return self._yearly_amount(obj.gross_salary)

    def get_yearly_net(self, obj):
        return self._yearly_amount(obj.net_salary)

    def validate_employee(self, value):
        queryset = Salary.objects.filter(employee=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError(
                "Salary already set for this employee."
            )
        return value


class SalarySerializer(EmployeeSalarySerializer):
    class Meta(EmployeeSalarySerializer.Meta):
        pass


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
            "basic",
            "da",
            "hra",
            "conveyance",
            "medical",
            "special_allowance",
            "gross_salary",
            "lop_days",
            "lop_deduction",
            "employee_pf",
            "employee_esi",
            "professional_tax",
            "tds_amount",
            "medical_insurance",
            "fixed_deductions",
            "employer_pf",
            "employer_esi",
            "net_pay",
            "status",
            "paid_on",
            "paid_date",
            "bank_reference",
        ]


class SalaryRevisionSerializer(serializers.ModelSerializer):

    class Meta:
        model = SalaryRevision
        fields = "__all__"


class PayrollStatusItemSerializer(serializers.ModelSerializer):
    employee = serializers.CharField(source="employee.employee_id", read_only=True)
    employee_name = serializers.SerializerMethodField()
    department = serializers.CharField(source="employee.department", read_only=True)
    account_number = serializers.CharField(source="employee.account_number", read_only=True)
    ifsc = serializers.CharField(source="employee.ifsc", read_only=True)
    month = serializers.SerializerMethodField()
    year = serializers.SerializerMethodField()

    class Meta:
        model = Payslip
        fields = [
            "id",
            "employee",
            "employee_name",
            "month",
            "year",
            "net_pay",
            "status",
            "department",
            "account_number",
            "ifsc",
            "paid_date",
            "bank_reference",
        ]

    def get_employee_name(self, obj):
        return f"{obj.employee.first_name} {obj.employee.last_name}".strip()

    def get_month(self, obj):
        return obj.month.strftime("%Y-%m")

    def get_year(self, obj):
        return obj.month.year


class ApprovePayrollSerializer(serializers.Serializer):
    month = serializers.RegexField(
        regex=r"^\d{4}-\d{2}$",
        error_messages={"invalid": "month must be in YYYY-MM format."},
    )


class MarkPayslipPaidSerializer(serializers.Serializer):
    payslip_id = serializers.IntegerField()
    bank_reference = serializers.CharField(required=False, allow_blank=True, max_length=100)