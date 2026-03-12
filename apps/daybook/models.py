from django.db import models
from django.conf import settings

class Vendor(models.Model):
    VENDOR_TYPE_CHOICES = (
        ("SUPPLIER", "Supplier"),
        ("CLIENT", "Client"),
        ("SERVICE", "Service Provider"),
    )

    name = models.CharField(max_length=200, unique=True)
    vendor_type = models.CharField(max_length=20, choices=VENDOR_TYPE_CHOICES, default="SUPPLIER")
    contact_person = models.CharField(max_length=100, blank=True, null=True)
    phone = models.CharField(max_length=15, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    
    # GST Details
    gst_applicable = models.BooleanField(default=False)
    gstin = models.CharField(max_length=15, blank=True, null=True)
    
    # Bank Details
    bank_name = models.CharField(max_length=100, blank=True, null=True)
    account_number = models.CharField(max_length=50, blank=True, null=True)
    ifsc_code = models.CharField(max_length=11, blank=True, null=True)
    account_holder_name = models.CharField(max_length=200, blank=True, null=True)
    
    # UPI Details
    upi_id = models.CharField(max_length=100, blank=True, null=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['vendor_type']),
        ]

    def __str__(self):
        return self.name


class Category(models.Model):
    CATEGORY_TYPE_CHOICES = (
        ("EXPENSE", "Expense"),
        ("INCOME", "Income"),
    )

    name = models.CharField(max_length=100, unique=True)
    category_type = models.CharField(max_length=20, choices=CATEGORY_TYPE_CHOICES, default="EXPENSE")
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name


class Transaction(models.Model):
    PAYMENT_MODE_CHOICES = (
        ("CASH", "Cash"),
        ("BANK", "Bank"),
        ("UPI", "UPI"),
        ("CHEQUE", "Cheque"),
    )

    date = models.DateField(db_index=True)
    details = models.TextField()
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="transactions")
    payment_mode = models.CharField(max_length=20, choices=PAYMENT_MODE_CHOICES, default="CASH")
    
    debit_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, default=0)
    credit_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, default=0)
    bank_withdraw = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, default=0)
    
    from_vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT, related_name="transactions_from", null=True, blank=True)
    to_vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT, related_name="transactions_to", null=True, blank=True)
    
    gst_applicable = models.BooleanField(default=False)
    gst_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, default=0)
    
    # Payment mode specific fields
    bank_name = models.CharField(max_length=100, blank=True, null=True)
    account_number = models.CharField(max_length=50, blank=True, null=True)
    ifsc_code = models.CharField(max_length=11, blank=True, null=True)
    account_holder_name = models.CharField(max_length=200, blank=True, null=True)
    upi_id = models.CharField(max_length=100, blank=True, null=True)
    cheque_number = models.CharField(max_length=50, blank=True, null=True)
    
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['date']),
            models.Index(fields=['category']),
            models.Index(fields=['payment_mode']),
            models.Index(fields=['-date']),
        ]

    def __str__(self):
        return f"{self.date} - {self.details[:50]}"
