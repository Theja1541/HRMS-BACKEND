import decimal
import json

from django.db import transaction
from rest_framework import serializers

from apps.payroll.models import Salary
from apps.payroll.serializers import EmployeeSalarySerializer, SalaryRevisionSerializer
from apps.payroll.services.payroll_service import (
    PAYROLL_COMPONENT_FIELDS,
    build_salary_record,
    money,
)
from .models import Employee

EMPLOYEE_MODEL_FIELDS = [field.name for field in Employee._meta.fields]
SALARY_WRITABLE_FIELDS = set(PAYROLL_COMPONENT_FIELDS)


# Lenient JSONField for handling HTML form submissions that send empty strings
class LenientJSONField(serializers.JSONField):
    def to_internal_value(self, data):
        if data in (None, "", "null"):
            return []
        return super().to_internal_value(data)


def parse_salary_payload(raw_salary):
    if raw_salary in [None, "", {}]:
        return None

    if isinstance(raw_salary, str):
        try:
            raw_salary = json.loads(raw_salary)
        except json.JSONDecodeError as exc:
            raise serializers.ValidationError(
                {"salary": "Invalid salary payload."}
            ) from exc

    if not hasattr(raw_salary, "items"):
        raise serializers.ValidationError(
            {"salary": "Salary payload must be an object."}
        )

    cleaned_salary = {}
    salary_errors = {}

    for key in SALARY_WRITABLE_FIELDS:
        if key not in raw_salary:
            continue

        try:
            cleaned_salary[key] = money(raw_salary.get(key))
        except (ValueError, TypeError, decimal.InvalidOperation):
            salary_errors[key] = "Enter a valid amount."

    if salary_errors:
        raise serializers.ValidationError({"salary": salary_errors})

    return cleaned_salary or None


def save_employee_salary(employee, salary_data):
    if salary_data is None:
        return None

    defaults = {**build_salary_record(salary_data)}
    if getattr(employee, "company_id", None):
        defaults["company_id"] = employee.company_id

    try:
        salary_obj, _ = Salary.objects.update_or_create(
            employee=employee,
            defaults=defaults,
        )
        return salary_obj
    except Exception as exc:
        # If DB schema is out-of-sync (missing columns) or other DB error occurs,
        # log and continue so employee creation/updates do not fail.
        import logging
        logger = logging.getLogger(__name__)
        logger.exception("Could not persist Salary for employee %s: %s", getattr(employee, 'id', None), exc)
        return None

# ============================================================
# EMPLOYEE LIST SERIALIZER (Lightweight – For Table View)
# ============================================================

class EmployeeListSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = EMPLOYEE_MODEL_FIELDS + ["full_name", "status", "role"]

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name or ''}".strip()

    def get_status(self, obj):
        return "Active" if obj.is_active else "Inactive"

    def get_role(self, obj):
        return getattr(obj.user, "role", "EMPLOYEE")


# ============================================================
# EMPLOYEE DETAIL SERIALIZER (Full Profile View)
# ============================================================


class EmployeeDetailSerializer(serializers.ModelSerializer):

    full_name = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()

    # Use a lenient JSON field for history so empty strings from forms
    # are accepted and normalized to an empty list instead of raising.
    history = LenientJSONField(required=False)


    salary = EmployeeSalarySerializer(read_only=True)
    salary_history = SalaryRevisionSerializer(many=True, read_only=True)

    class Meta:
        model = Employee
        fields = EMPLOYEE_MODEL_FIELDS + [
            "full_name",
            "status",
            "role",
            "salary",
            "salary_history",
        ]
        read_only_fields = ["user"]

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name or ''}".strip()

    def get_status(self, obj):
        return "Active" if obj.is_active else "Inactive"

    def get_role(self, obj):
        return getattr(obj.user, "role", "EMPLOYEE")

    def _parse_salary_payload(self):
        return parse_salary_payload(self.initial_data.get("salary"))

    def validate_mobile(self, value):
        if value and not str(value).isdigit():
            raise serializers.ValidationError("Mobile must contain only digits.")
        if value and len(str(value)) not in (10, 12, 13, 15):
            raise serializers.ValidationError("Enter a valid mobile number.")
        return value

    def validate_reporting_manager(self, value):
        return (value or "").strip()

    def validate_pan(self, value):
        pan = (value or "").strip().upper()
        if pan and len(pan) != 10:
            raise serializers.ValidationError("PAN must be 10 characters.")
        return pan

    def validate_ifsc(self, value):
        ifsc = (value or "").strip().upper()
        if ifsc and len(ifsc) != 11:
            raise serializers.ValidationError("IFSC must be 11 characters.")
        return ifsc

    def validate_pf_number(self, value):
        pf_number = (value or "").strip()
        if len(pf_number) > 50:
            raise serializers.ValidationError("PF Number must be 50 characters or fewer.")
        return pf_number or None

    def validate_uan_number(self, value):
        uan_number = "".join(ch for ch in str(value or "").strip() if ch.isdigit())
        if uan_number and len(uan_number) != 12:
            raise serializers.ValidationError("UAN must be exactly 12 digits.")
        return uan_number or None

    def validate_emergency_number(self, value):
        emergency_number = (value or "").strip()
        if emergency_number and not emergency_number.isdigit():
            raise serializers.ValidationError("Emergency number must contain only digits.")
        return emergency_number

    def validate(self, attrs):
        attrs["_salary_payload"] = self._parse_salary_payload()

        # Handle history JSONField coming from HTML form inputs.
        # When submitted from a form the frontend may send an empty string for
        # JSON fields which triggers DRF/Django to raise "Value must be valid JSON.".
        # Normalize common cases here so updates don't fail.
        raw_history = self.initial_data.get("history", None)

        # If the serializer already parsed `history`, leave it alone.
        if "history" not in attrs:
            if raw_history in (None, "", [], "null"):
                attrs["history"] = []
            elif isinstance(raw_history, str):
                try:
                    parsed = json.loads(raw_history)
                except json.JSONDecodeError:
                    raise serializers.ValidationError({"history": "Value must be valid JSON."})
                attrs["history"] = parsed

        return attrs

    # ================= CREATE =================

    @transaction.atomic
    def create(self, validated_data):
        salary_data = validated_data.pop("_salary_payload", None)

        employee = Employee.objects.create(**validated_data)

        if salary_data is not None:
            save_employee_salary(employee, salary_data)

        return employee


    # ================= UPDATE =================

    @transaction.atomic
    def update(self, instance, validated_data):
        salary_data = validated_data.pop("_salary_payload", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        if salary_data is not None:
            save_employee_salary(instance, salary_data)

        return instance