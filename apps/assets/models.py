from django.db import models
from django.conf import settings
from apps.employees.models import Employee


class CompanyAsset(models.Model):
    ASSET_TYPE_CHOICES = (
        ('LAPTOP', 'Laptop'),
        ('MOBILE', 'Mobile'),
        ('ID_CARD', 'ID Card'),
        ('MONITOR', 'Monitor'),
        ('OTHER', 'Other'),
    )

    asset_name = models.CharField(max_length=200)
    asset_type = models.CharField(max_length=50, choices=ASSET_TYPE_CHOICES)
    serial_number = models.CharField(max_length=100, blank=True)
    purchase_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['asset_type']),
        ]

    def __str__(self):
        return f"{self.asset_name} ({self.asset_type})"


class AssetAssignment(models.Model):
    STATUS_CHOICES = (
        ('ASSIGNED', 'Assigned'),
        ('RETURNED', 'Returned'),
    )

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='asset_assignments')
    asset = models.ForeignKey(CompanyAsset, on_delete=models.CASCADE, related_name='assignments')
    assigned_date = models.DateField()
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ASSIGNED', db_index=True)
    returned_date = models.DateField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['employee', 'status']),
        ]

    def __str__(self):
        return f"{self.employee.employee_id} - {self.asset.asset_name} ({self.status})"


class AssetReturnRequest(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    )

    CONDITION_CHOICES = (
        ('GOOD', 'Good'),
        ('DAMAGED', 'Damaged'),
        ('NOT_WORKING', 'Not Working'),
    )

    ASSET_TYPE_CHOICES = (
        ('LAPTOP', 'Laptop'),
        ('MOBILE', 'Mobile'),
        ('ID_CARD', 'ID Card'),
        ('MONITOR', 'Monitor'),
        ('OTHER', 'Other'),
    )

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='asset_return_requests', db_index=True)
    asset_type = models.CharField(max_length=50, choices=ASSET_TYPE_CHOICES)
    asset_name = models.CharField(max_length=200)
    serial_number = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES)
    return_date = models.DateField()
    comments = models.TextField(blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', db_index=True)
    request_date = models.DateTimeField(auto_now_add=True)
    
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_asset_returns')
    approval_date = models.DateTimeField(null=True, blank=True)
    admin_remarks = models.TextField(blank=True)

    class Meta:
        ordering = ['-request_date']
        indexes = [
            models.Index(fields=['employee', 'status']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.employee.employee_id} - {self.asset_name} ({self.status})"
