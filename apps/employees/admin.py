from django.contrib import admin
from .models import Employee


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = (
        "employee_id",
        "full_name",
        "first_name",
        "last_name",
        "email",
        "department",
        "designation",
        "is_active",
        "updated_at",
        "created_at",
    )
    list_filter = (
        "department",
        "designation",
        "is_active",
        "employment_type",
        "pf_applicable",
        "esi_applicable",
        "pt_applicable",
    )
    search_fields = (
        "employee_id",
        "first_name",
        "last_name",
        "email",
        "mobile",
        "department",
        "designation",
    )
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")
    list_per_page = 50
    list_select_related = ("user",)







