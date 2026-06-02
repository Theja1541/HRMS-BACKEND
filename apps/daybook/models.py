from django.db import models
from django.conf import settings
from apps.accounts.models import Company

class ActiveManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)

class Vendor(models.Model):
    VENDOR_TYPE_CHOICES = (
        ("SUPPLIER", "Supplier"),
        ("CLIENT", "Client"),
        ("SERVICE", "Service Provider"),
    )

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="daybook_vendors", null=True, blank=True)
    name = models.CharField(max_length=200)
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
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ActiveManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['vendor_type']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'name'],
                condition=models.Q(is_deleted=False),
                name='unique_company_vendor_name'
            )
        ]

    def __str__(self):
        return self.name


class Category(models.Model):
    CATEGORY_TYPE_CHOICES = (
        ("EXPENSE", "Expense"),
        ("INCOME", "Income"),
    )

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="daybook_categories", null=True, blank=True)
    name = models.CharField(max_length=100)
    category_type = models.CharField(max_length=20, choices=CATEGORY_TYPE_CHOICES, default="EXPENSE")
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = "Categories"
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'name'],
                name='unique_company_category_name'
            )
        ]

    def __str__(self):
        return self.name


class Transaction(models.Model):
    PAYMENT_MODE_CHOICES = (
        ("CASH", "Cash"),
        ("BANK", "Bank"),
        ("UPI", "UPI"),
        ("CHEQUE", "Cheque"),
    )

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="daybook_transactions", null=True, blank=True)
    transaction_number = models.CharField(max_length=50, blank=True, null=True)
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
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, default=0)
    gst_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, default=0)
    
    # HSN Code
    hsn_code = models.CharField(max_length=50, blank=True, null=True)
    
    # Payment mode specific fields
    bank_name = models.CharField(max_length=100, blank=True, null=True)
    account_number = models.CharField(max_length=50, blank=True, null=True)
    ifsc_code = models.CharField(max_length=11, blank=True, null=True)
    account_holder_name = models.CharField(max_length=200, blank=True, null=True)
    upi_id = models.CharField(max_length=100, blank=True, null=True)
    cheque_number = models.CharField(max_length=50, blank=True, null=True)
    
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ActiveManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['date']),
            models.Index(fields=['category']),
            models.Index(fields=['payment_mode']),
            models.Index(fields=['-date']),
        ]
        constraints = [
            models.CheckConstraint(
                check=(
                    (models.Q(debit_amount__gt=0) & (models.Q(credit_amount=0) | models.Q(credit_amount__isnull=True))) |
                    (models.Q(credit_amount__gt=0) & (models.Q(debit_amount=0) | models.Q(debit_amount__isnull=True)))
                ),
                name='daybook_transaction_amount_check'
            ),
            models.UniqueConstraint(
                fields=['company', 'transaction_number'],
                name='unique_company_transaction_number'
            )
        ]

    def __str__(self):
        return f"{self.date} - {self.details[:50]}"


def seed_default_categories_for_company(company):
    DEFAULT_CATEGORIES = [
        ("Rent", "EXPENSE"),
        ("Salaries", "EXPENSE"),
        ("Utility Bills", "EXPENSE"),
        ("Software & Subscriptions", "EXPENSE"),
        ("Office Supplies", "EXPENSE"),
        ("Travel & Lodging", "EXPENSE"),
        ("Marketing & Advertising", "EXPENSE"),
        ("Miscellaneous Expense", "EXPENSE"),
        ("Client Billing", "INCOME"),
        ("Product Sales", "INCOME"),
        ("Consulting Services", "INCOME"),
        ("Interest Income", "INCOME"),
        ("Other Income", "INCOME"),
    ]
    created = []
    for name, cat_type in DEFAULT_CATEGORIES:
        obj, created_new = Category.objects.get_or_create(
            company=company,
            name=name,
            defaults={"category_type": cat_type}
        )
        if created_new:
            created.append(obj)
    return created

class TransactionItem(models.Model):
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name="items")
    product_name = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    gst_applicable = models.BooleanField(default=False)
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, default=0)
    gst_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, default=0)
    
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    hsn_code = models.CharField(max_length=50, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.product_name} ({self.quantity} x {self.unit_price})"

