from django.contrib import admin
from .models import CompanyAsset, AssetAssignment, AssetReturnRequest


@admin.register(CompanyAsset)
class CompanyAssetAdmin(admin.ModelAdmin):
    list_display = ['asset_name', 'asset_type', 'serial_number', 'purchase_date']
    list_filter = ['asset_type']
    search_fields = ['asset_name', 'serial_number']


@admin.register(AssetAssignment)
class AssetAssignmentAdmin(admin.ModelAdmin):
    list_display = ['employee', 'asset', 'assigned_date', 'status']
    list_filter = ['status', 'assigned_date']
    search_fields = ['employee__employee_id', 'asset__asset_name']


@admin.register(AssetReturnRequest)
class AssetReturnRequestAdmin(admin.ModelAdmin):
    list_display = ['employee', 'asset_name', 'asset_type', 'condition', 'status', 'request_date']
    list_filter = ['status', 'asset_type', 'condition', 'request_date']
    search_fields = ['employee__employee_id', 'asset_name', 'serial_number']
