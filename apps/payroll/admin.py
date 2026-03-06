from django.contrib import admin
from .models import Salary, Payslip


@admin.register(Salary)
class SalaryAdmin(admin.ModelAdmin):
    list_display = ("employee", "basic", "hra", "da", "conveyance", "medical")
    search_fields = ("employee__first_name",)


@admin.register(Payslip)
class PayslipAdmin(admin.ModelAdmin):
    list_display = ("employee", "month", "gross_salary", "net_pay", "status")
    list_filter = ("status", "month")