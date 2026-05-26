from django.db import models
from django.conf import settings
from apps.employees.models import Employee


class Asset(models.Model):
    """Unified Asset model consolidating CompanyAsset, AssetAssignment, and AssetReturnRequest.
    Tracks assignment state and history as JSON.
    """

    ASSET_TYPE_CHOICES = (
        ("LAPTOP", "Laptop"),
        ("MOBILE", "Mobile"),
        ("ID_CARD", "ID Card"),
        ("MONITOR", "Monitor"),
        ("OTHER", "Other"),
    )

    STATUS_CHOICES = (
        ("ASSIGNED", "Assigned"),
        ("RETURNED", "Returned"),
        ("PENDING", "Pending"),
    )

    asset_name = models.CharField(max_length=200)
    asset_type = models.CharField(max_length=50, choices=ASSET_TYPE_CHOICES)
    serial_number = models.CharField(max_length=100, blank=True)
    purchase_date = models.DateField(null=True, blank=True)

    # Owner information – an asset may be assigned directly to an employee
    employee = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assets",
    )

    # Assignment metadata
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_assets",
    )
    assigned_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING", db_index=True)
    returned_date = models.DateField(null=True, blank=True)

    # History of state changes – list of dicts {"status":..., "date":..., "by":...}
    history = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["asset_type"]),
            models.Index(fields=["employee", "status"]),
        ]

    def __str__(self):
        return f"{self.asset_name} ({self.asset_type})"

    def assign(self, employee, user):
        """Assign asset to an employee and record history."""
        self.employee = employee
        self.assigned_by = user
        self.assigned_date = models.functions.Now()
        self.status = "ASSIGNED"
        self.history.append({
            "status": "ASSIGNED",
            "date": models.functions.Now().isoformat(),
            "by": user.id if user else None,
        })
        self.save(update_fields=["employee", "assigned_by", "assigned_date", "status", "history"])

    def return_asset(self, user):
        """Mark asset as returned and record history."""
        self.status = "RETURNED"
        self.returned_date = models.functions.Now()
        self.history.append({
            "status": "RETURNED",
            "date": models.functions.Now().isoformat(),
            "by": user.id if user else None,
        })
        self.save(update_fields=["status", "returned_date", "history"])


class AssetReturnRequest(models.Model):
    """Model representing a request for returning an asset."""
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='return_requests', null=True, blank=True)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='asset_return_requests')
    request_date = models.DateTimeField(auto_now_add=True)
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('RETURNED', 'Returned'),
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    admin_remarks = models.TextField(blank=True, null=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='approved_return_requests')
    approval_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-request_date']

    def __str__(self):
        return f"ReturnRequest #{self.id} for {self.asset.asset_name}"
