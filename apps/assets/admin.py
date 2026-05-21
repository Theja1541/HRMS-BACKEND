from django.contrib import admin
from .models import Asset


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = (
        "asset_name",
        "asset_type",
        "serial_number",
        "purchase_date",
        "employee",
        "status",
        "assigned_date",
        "returned_date",
    )
    list_filter = (
        "asset_type",
        "status",
    )
    search_fields = (
        "asset_name",
        "serial_number",
        "employee__employee_id",
    )
    readonly_fields = ("created_at", "updated_at")
