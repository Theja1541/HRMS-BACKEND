from rest_framework import serializers
from apps.billing.models import SubscriptionPlan, CompanySubscription, PaymentTransaction, GSTInvoice

class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "monthly_price",
            "yearly_price",
            "gst_percentage",
            "employee_limit",
            "features_json",
            "razorpay_plan_id",
            "razorpay_plan_yearly_id",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class CompanySubscriptionSerializer(serializers.ModelSerializer):
    plan_details = SubscriptionPlanSerializer(source="subscription_plan", read_only=True)
    company_name = serializers.CharField(source="company.name", read_only=True)

    class Meta:
        model = CompanySubscription
        fields = [
            "id",
            "company",
            "company_name",
            "subscription_plan",
            "plan_details",
            "billing_cycle",
            "start_date",
            "end_date",
            "next_billing_date",
            "is_active",
            "payment_status",
            "razorpay_subscription_id",
            "auto_renew",
            "trial_start",
            "trial_end",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "is_active", "payment_status", "created_at", "updated_at"]


class PaymentTransactionSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source="company.name", read_only=True)
    plan_name = serializers.CharField(source="subscription.subscription_plan.name", read_only=True, allow_null=True)
    invoice_download_url = serializers.SerializerMethodField()

    class Meta:
        model = PaymentTransaction
        fields = [
            "id",
            "company",
            "company_name",
            "subscription",
            "plan_name",
            "razorpay_order_id",
            "razorpay_payment_id",
            "razorpay_signature",
            "amount",
            "gst_amount",
            "total_amount",
            "currency",
            "payment_method",
            "payment_status",
            "paid_at",
            "invoice_number",
            "failure_reason",
            "invoice_download_url",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "invoice_download_url", "created_at", "updated_at"]

    def get_invoice_download_url(self, obj):
        if hasattr(obj, "gst_invoice") and obj.gst_invoice.invoice_pdf:
            return obj.gst_invoice.invoice_pdf.url
        return None


class GSTInvoiceSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source="company.name", read_only=True)
    pdf_url = serializers.FileField(source="invoice_pdf", read_only=True)

    class Meta:
        model = GSTInvoice
        fields = [
            "id",
            "invoice_number",
            "company",
            "company_name",
            "payment_transaction",
            "gst_percentage",
            "gst_amount",
            "subtotal",
            "total",
            "pdf_url",
            "issued_at",
            "created_at",
        ]
