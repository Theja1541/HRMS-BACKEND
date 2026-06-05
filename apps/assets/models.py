from django.db import models
from django.conf import settings
from apps.employees.models import Employee
from django.utils import timezone
import uuid


class AssetCategory(models.Model):
    company = models.ForeignKey(
        "accounts.Company", on_delete=models.CASCADE, null=True, blank=True, related_name="asset_categories"
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Asset Categories"
        unique_together = (("company", "name"),)

    def __str__(self):
        return self.name


class Asset(models.Model):
    STATUS_CHOICES = (
        ("AVAILABLE", "Available"),
        ("ASSIGNED", "Assigned"),
        ("RETURNED", "Returned"),
        ("MAINTENANCE", "Maintenance"),
        ("LOST", "Lost"),
        ("DAMAGED", "Damaged"),
        ("RETIRED", "Retired"),
    )

    company = models.ForeignKey(
        "accounts.Company", on_delete=models.CASCADE, null=True, blank=True, related_name="assets"
    )
    asset_code = models.CharField(max_length=100, unique=True, blank=True)
    asset_name = models.CharField(max_length=200)
    category = models.ForeignKey(AssetCategory, on_delete=models.SET_NULL, null=True, related_name="assets")
    serial_number = models.CharField(max_length=100, unique=True)
    asset_tag = models.CharField(max_length=100, unique=True)
    brand = models.CharField(max_length=100, blank=True)
    model = models.CharField(max_length=100, blank=True)
    purchase_date = models.DateField(null=True, blank=True)
    purchase_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    warranty_expiry = models.DateField(null=True, blank=True)
    vendor_name = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="AVAILABLE")
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="created_assets"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.asset_code} - {self.asset_name}"

    def save(self, *args, **kwargs):
        if not self.asset_code:
            self.asset_code = f"AST-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)


class AssetAssignment(models.Model):
    STATUS_CHOICES = (
        ("ACTIVE", "Active"),
        ("RETURNED", "Returned"),
    )

    company = models.ForeignKey(
        "accounts.Company", on_delete=models.CASCADE, null=True, blank=True, related_name="asset_assignments"
    )
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="assignments")
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="asset_assignments")
    assigned_date = models.DateField(default=timezone.localdate)
    expected_return_date = models.DateField(null=True, blank=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="asset_assignments"
    )
    remarks = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ACTIVE")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.asset.asset_code} to {self.employee}"


class AssetReturn(models.Model):
    CONDITION_CHOICES = (
        ("GOOD", "Good"),
        ("DAMAGED", "Damaged"),
        ("LOST", "Lost"),
        ("NEEDS_REPAIR", "Needs Repair"),
    )

    company = models.ForeignKey(
        "accounts.Company", on_delete=models.CASCADE, null=True, blank=True, related_name="asset_returns"
    )
    assignment = models.OneToOneField(AssetAssignment, on_delete=models.CASCADE, related_name="return_record")
    returned_by = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, related_name="asset_returns")
    return_date = models.DateField(default=timezone.localdate)
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES)
    remarks = models.TextField(blank=True)
    recovery_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    cleared_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='asset_clearances')
    cleared_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Return for {self.assignment.asset.asset_code}"


class AssetMaintenance(models.Model):
    STATUS_CHOICES = (
        ("OPEN", "Open"),
        ("IN_PROGRESS", "In Progress"),
        ("COMPLETED", "Completed"),
    )

    company = models.ForeignKey(
        "accounts.Company", on_delete=models.CASCADE, null=True, blank=True, related_name="asset_maintenances"
    )
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="maintenances")
    maintenance_type = models.CharField(max_length=100)
    service_vendor = models.CharField(max_length=200, blank=True)
    service_date = models.DateField(default=timezone.localdate)
    cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    remarks = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="OPEN")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="created_maintenances"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Maintenance {self.id} for {self.asset.asset_code}"


class AssetHistory(models.Model):
    ACTION_CHOICES = (
        ("CREATED", "Created"),
        ("UPDATED", "Updated"),
        ("ASSIGNED", "Assigned"),
        ("RETURNED", "Returned"),
        ("MAINTENANCE", "Maintenance"),
        ("LOST", "Lost"),
        ("DAMAGED", "Damaged"),
        ("RETIRED", "Retired"),
    )

    company = models.ForeignKey(
        "accounts.Company", on_delete=models.CASCADE, null=True, blank=True, related_name="asset_histories"
    )
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="history")
    action_type = models.CharField(max_length=20, choices=ACTION_CHOICES)
    employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name="asset_history_events")
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="asset_actions"
    )
    description = models.TextField(blank=True)
    action_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.action_type} on {self.asset.asset_code}"


class AssetRequest(models.Model):
    REQUEST_TYPE_CHOICES = (
        ("ALLOCATION", "Allocation"),
        ("RETURN", "Return"),
    )
    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
    )

    company = models.ForeignKey(
        "accounts.Company", on_delete=models.CASCADE, null=True, blank=True, related_name="asset_requests"
    )
    asset = models.ForeignKey(Asset, on_delete=models.SET_NULL, null=True, blank=True, related_name="requests")
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="asset_requests")
    request_type = models.CharField(max_length=20, choices=REQUEST_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    employee_remarks = models.TextField(blank=True)
    admin_remarks = models.TextField(blank=True)
    request_date = models.DateTimeField(auto_now_add=True)
    approval_date = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_asset_requests"
    )

    def __str__(self):
        return f"{self.request_type} request by {self.employee} for {self.asset}"
