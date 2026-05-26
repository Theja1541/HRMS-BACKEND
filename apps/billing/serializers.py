from rest_framework import serializers
from .models import PricingPlan, Payment, Invoice


class PricingPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = PricingPlan
        fields = [
            "id",
            "name",
            "code",
            "description",
            "price_monthly",
            "currency",
            "max_employees",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class PaymentSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source="company.name", read_only=True)
    company_code = serializers.CharField(source="company.company_code", read_only=True)
    plan_name = serializers.CharField(
        source="pricing_plan.name", read_only=True, allow_null=True
    )

    class Meta:
        model = Payment
        fields = [
            "id",
            "company",
            "company_name",
            "company_code",
            "pricing_plan",
            "plan_name",
            "amount",
            "currency",
            "status",
            "payment_date",
            "reference",
            "notes",
            "created_at",
        ]
        read_only_fields = ["created_at"]


class InvoiceSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source="company.name", read_only=True)
    company_code = serializers.CharField(source="company.company_code", read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "id",
            "company",
            "company_name",
            "company_code",
            "invoice_number",
            "amount",
            "currency",
            "issued_at",
            "due_date",
            "status",
            "payment",
            "notes",
            "created_at",
        ]
        read_only_fields = ["created_at"]
