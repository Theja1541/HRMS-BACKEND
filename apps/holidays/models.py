from django.db import models
from django.utils.translation import gettext_lazy as _

class Holiday(models.Model):
    HOLIDAY_TYPES = (
        ("PUBLIC", "Public Holiday"),
        ("OPTIONAL", "Optional Holiday"),
        ("COMPANY", "Company Holiday"),
        ("FESTIVAL", "Festival"),
    )

    STATE_CHOICES = (
        ("ALL", "All States"),
        ("AP", "Andhra Pradesh"),
        ("TS", "Telangana"),
        ("KA", "Karnataka"),
        ("TN", "Tamil Nadu"),
        ("MH", "Maharashtra"),
    )

    PAYMENT_TYPES = (
        ("PAID", "Paid"),
        ("UNPAID", "Unpaid"),
    )

    company = models.ForeignKey(
        "accounts.Company",
        on_delete=models.CASCADE,
        related_name="holidays",
        null=True,
        blank=True
    )
    
    holiday_name = models.CharField(max_length=255)
    from_date = models.DateField()
    to_date = models.DateField(null=True, blank=True)
    holiday_type = models.CharField(max_length=20, choices=HOLIDAY_TYPES, default="PUBLIC")
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPES, default="PAID")
    description = models.TextField(blank=True, null=True)
    
    state = models.CharField(max_length=50, choices=STATE_CHOICES, default="ALL")
    country = models.CharField(max_length=50, default="India")
    
    is_recurring = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        related_name="created_holidays",
        null=True,
        blank=True
    )
    updated_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        related_name="updated_holidays",
        null=True,
        blank=True
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["from_date"]
        # Allow multiple holidays with the same name/date for different states or companies
        indexes = [
            models.Index(fields=["from_date"]),
            models.Index(fields=["company"]),
            models.Index(fields=["state"]),
        ]

    def __str__(self):
        return f"{self.holiday_name} - {self.from_date}"

    def save(self, *args, **kwargs):
        if not self.to_date:
            self.to_date = self.from_date
        super().save(*args, **kwargs)
