from decimal import Decimal
from django.db import models


class SubscriptionPlan(models.Model):
    """SaaS Subscription Plan config."""
    name = models.CharField(max_length=100)
    slug = models.CharField(max_length=100, unique=True, db_index=True)
    description = models.TextField(blank=True)
    monthly_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    yearly_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    gst_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("18.00"))
    employee_limit = models.PositiveIntegerField(null=True, blank=True, help_text="Null means unlimited employees")
    features_json = models.JSONField(default=dict, blank=True, help_text="Dictionary of active module permissions")
    razorpay_plan_id = models.CharField(max_length=255, null=True, blank=True)
    razorpay_plan_yearly_id = models.CharField(max_length=255, null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["monthly_price"]

    def __str__(self):
        return f"{self.name} (Slug: {self.slug})"


class CompanySubscription(models.Model):
    """Subscription instance mapping a tenant company to a SubscriptionPlan."""
    company = models.OneToOneField(
        "accounts.Company",
        on_delete=models.CASCADE,
        related_name="subscription",
    )
    subscription_plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name="company_subscriptions",
    )
    billing_cycle = models.CharField(
        max_length=20,
        choices=[("monthly", "Monthly"), ("yearly", "Yearly")],
        default="monthly",
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    next_billing_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    payment_status = models.CharField(max_length=50, default="pending", db_index=True)
    razorpay_subscription_id = models.CharField(max_length=255, null=True, blank=True)
    auto_renew = models.BooleanField(default=True)
    trial_start = models.DateField(null=True, blank=True)
    trial_end = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-end_date"]

    def __str__(self):
        return f"{self.company.name} - {self.subscription_plan.name} ({self.billing_cycle})"


class PaymentTransaction(models.Model):
    """Payment transactions made by tenant companies for subscription orders."""
    STATUS_PENDING = "pending"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
    ]

    company = models.ForeignKey(
        "accounts.Company",
        on_delete=models.CASCADE,
        related_name="subscription_transactions",
    )
    subscription = models.ForeignKey(
        CompanySubscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
    )
    razorpay_order_id = models.CharField(max_length=255, unique=True, db_index=True)
    razorpay_payment_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    razorpay_signature = models.CharField(max_length=255, null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    gst_amount = models.DecimalField(max_digits=12, decimal_places=2)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default="INR")
    payment_method = models.CharField(max_length=50, null=True, blank=True)
    payment_status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    invoice_number = models.CharField(max_length=100, null=True, blank=True)
    failure_reason = models.TextField(null=True, blank=True)
    raw_response_json = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.company.name} - Order {self.razorpay_order_id} ({self.payment_status})"


class GSTInvoice(models.Model):
    """Chronological GST-compliant Invoice created post successful payment."""
    invoice_number = models.CharField(max_length=100, unique=True, db_index=True)
    company = models.ForeignKey(
        "accounts.Company",
        on_delete=models.CASCADE,
        related_name="subscription_invoices",
    )
    payment_transaction = models.OneToOneField(
        PaymentTransaction,
        on_delete=models.CASCADE,
        related_name="gst_invoice",
    )
    gst_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("18.00"))
    gst_amount = models.DecimalField(max_digits=12, decimal_places=2)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    invoice_pdf = models.FileField(upload_to="subscription_invoices/", null=True, blank=True)
    issued_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-issued_at"]

    def __str__(self):
        return f"Invoice {self.invoice_number} - {self.company.name}"


class RazorpayWebhookLog(models.Model):
    """Raw logs of all incoming Razorpay webhooks to prevent duplicate actions."""
    event_type = models.CharField(max_length=100, db_index=True)
    payload = models.JSONField()
    signature = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=50, default="received", db_index=True)
    received_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-received_at"]

    def __str__(self):
        return f"Webhook {self.event_type} - {self.status}"


