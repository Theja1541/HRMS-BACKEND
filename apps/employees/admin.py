from django.contrib import admin
from .models import Employee, EmployeeHistory


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = (
        "employee_id",
        "first_name",
        "email",
        "department",
        "is_active",
        "created_at",
    )
    list_filter = (
        "department",
        "is_active",
    )
    search_fields = (
        "employee_id",
        "first_name",
        "last_name",
        "email",
    )
    ordering = ("-created_at",)


@admin.register(EmployeeHistory)
class EmployeeHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "employee",
        "field_name",
        "old_value",
        "new_value",
        "changed_at",
    )
    search_fields = ("employee__employee_id", "field_name")
    ordering = ("-changed_at",)