from django.contrib import admin
from .models import LeaveType, LeaveBalance, LeaveRequest, LeaveApprovalLog
from .models import Holiday


@admin.register(LeaveType)
class LeaveTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "annual_quota", "is_paid", "is_active")


@admin.register(LeaveBalance)
class LeaveBalanceAdmin(admin.ModelAdmin):
    list_display = ("employee", "leave_type", "year", "total_allocated", "used")


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ("employee", "leave_type", "start_date", "end_date", "status")
    list_filter = ("status", "leave_type")


@admin.register(LeaveApprovalLog)
class LeaveApprovalLogAdmin(admin.ModelAdmin):
    list_display = ("leave_request", "action", "performed_by", "performed_at")


@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ("name","date")