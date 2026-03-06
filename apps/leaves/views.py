from django.utils import timezone
from django.db import transaction
from rest_framework import status
from apps.accounts.permissions import IsEmployee, IsHR
from apps.employees.models import Employee
from .models import LeaveRequest, LeaveBalance, LeaveType, LeaveApprovalLog
from .serializers import LeaveRequestSerializer, LeaveBalanceSerializer
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from apps.accounts.permissions import IsEmployee, IsHR
from .models import LeaveType
from apps.leaves.models import LeaveRequest
from datetime import timedelta
from datetime import datetime
from django.db.models import Q
from apps.payroll.utils import is_payroll_closed, is_super_admin
from apps.accounts.permissions import IsEmployee
# from .services import sync_leave_to_attendance
from .utils import sync_leave_to_attendance
from apps.attendance.models import Attendance
from apps.leaves.services.leave_service import LeaveService


@api_view(["POST"])
@permission_classes([IsEmployee])
@transaction.atomic
def apply_leave(request):

    employee = request.user.employee_profile

    leave_type_id = request.data.get("leave_type")
    start_date = request.data.get("start_date")
    end_date = request.data.get("end_date")
    reason = request.data.get("reason")
    is_half_day = request.data.get("is_half_day", False)

    if not all([leave_type_id, start_date, end_date, reason]):
        return Response({"error": "All fields required"}, status=400)

    try:
        leave_type = LeaveType.objects.get(id=leave_type_id)
    except LeaveType.DoesNotExist:
        return Response({"error": "Invalid leave type"}, status=404)

    try:
        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
    except ValueError:
        return Response({"error": "Invalid date format (YYYY-MM-DD)"}, status=400)

    if start_date > end_date:
        return Response({"error": "Start date cannot be after end date"}, status=400)

    if start_date < datetime.now().date():
        return Response({"error": "Cannot apply leave for past dates"}, status=400)

    # Payroll lock check
    current = start_date
    while current <= end_date:
        if is_payroll_closed(current.year, current.month):
            return Response(
                {"error": "Cannot apply leave for payroll closed month"},
                status=400
            )
        current += timedelta(days=1)

    # Overlap check
    overlap = LeaveRequest.objects.filter(
        employee=employee,
        status__in=["PENDING", "APPROVED"],
        start_date__lte=end_date,
        end_date__gte=start_date,
    ).exists()

    if overlap:
        return Response(
            {"error": "Leave already applied for selected date range"},
            status=400
        )

    days = (end_date - start_date).days + 1

    if is_half_day:
        if days > 1:
            return Response(
                {"error": "Half day leave can only be for one day"},
                status=400
            )
        days = 0.5

    year = start_date.year

    if leave_type.is_paid:

        balance, _ = LeaveBalance.objects.select_for_update().get_or_create(
            employee=employee,
            leave_type=leave_type,
            year=year,
            defaults={
                "total_allocated": leave_type.annual_quota
            }
        )

        if balance.remaining < days:
            return Response(
                {"error": "Insufficient leave balance"},
                status=400
            )

    leave = LeaveRequest.objects.create(
        employee=employee,
        leave_type=leave_type,
        start_date=start_date,
        end_date=end_date,
        reason=reason,
        is_half_day=is_half_day
    )

    LeaveApprovalLog.objects.create(
        leave_request=leave,
        action="APPLIED",
        performed_by=request.user
    )

    return Response({"message": "Leave applied successfully"})

@api_view(["POST"])
@permission_classes([IsHR])
@transaction.atomic
def approve_leave(request, leave_id):

    try:
        leave = (
            LeaveRequest.objects
            .select_for_update()   # 🔒 row lock
            .get(id=leave_id)
        )
    except LeaveRequest.DoesNotExist:
        return Response({"error": "Leave not found"}, status=404)

    if leave.status != "PENDING":
        return Response({"error": "Leave already processed"}, status=400)

    # =========================================================
    # 🔒 PAYROLL LOCK CHECK
    # =========================================================
    current_date = leave.start_date

    while current_date <= leave.end_date:
        if (
            is_payroll_closed(current_date.year, current_date.month)
            and not is_super_admin(request.user)
        ):
            return Response(
                {"error": "Payroll month is CLOSED. Only Super Admin can override."},
                status=400
            )
        current_date += timedelta(days=1)

    # =========================================================
    # LEAVE BALANCE CHECK
    # =========================================================
    days = leave.total_days()
    year = leave.start_date.year

    balance = None

    if leave.leave_type.is_paid:

        balance, _ = LeaveBalance.objects.select_for_update().get_or_create(
            employee=leave.employee,
            leave_type=leave.leave_type,
            year=year,
            defaults={
                "total_allocated": leave.leave_type.annual_quota,
                "used": 0,
            }
        )

        if balance.remaining < days:
            return Response(
                {"error": "Insufficient leave balance"},
                status=400
            )

    # =========================================================
    # 🔄 SYNC ATTENDANCE FIRST (SAFER ORDER)
    # =========================================================
    try:
        sync_leave_to_attendance(leave)
    except Exception as e:
        return Response(
            {"error": f"Attendance sync failed: {str(e)}"},
            status=500
        )

    # =========================================================
    # NOW DEDUCT BALANCE
    # =========================================================
    if balance:
        balance.used += days
        balance.save(update_fields=["used"])

    # =========================================================
    # APPROVE LEAVE
    # =========================================================
    leave.status = "APPROVED"
    leave.approved_by = request.user
    leave.approved_on = timezone.now()
    leave.save(update_fields=["status", "approved_by", "approved_on"])

    LeaveApprovalLog.objects.create(
        leave_request=leave,
        action="APPROVED",
        performed_by=(
            request.user.employee_profile
            if hasattr(request.user, "employee_profile")
            else None
        )
    )

    return Response({"message": "Leave approved successfully & attendance synced"})


@api_view(["GET"])
@permission_classes([IsEmployee])
def my_leave_balance(request):

    employee = request.user.employee_profile
    year = timezone.now().year

    leave_types = LeaveService.get_employee_balances(
        employee=employee,
        year=year
    )

    data = [
        {
            "leave_type": lt.name,
            "total_allocated": lt.total_allocated,
            "used": lt.used,
            "remaining": lt.total_allocated - lt.used,
        }
        for lt in leave_types
    ]

    return Response(data)


@api_view(["GET"])
@permission_classes([IsHR])
def all_leave_requests(request):

    leaves = LeaveRequest.objects.all().order_by("-applied_on")
    serializer = LeaveRequestSerializer(leaves, many=True)
    return Response(serializer.data)

@api_view(["GET"])
@permission_classes([IsEmployee | IsHR])
def leave_types(request):
    types = LeaveType.objects.filter(is_active=True)

    data = [
    {
        "id": t.id,
        "name": t.name,
        "annual_quota": t.annual_quota,  # ✅ CORRECT
    }
    for t in types
]

    return Response(data)

@api_view(["GET"])
@permission_classes([IsEmployee])
def my_leaves(request):

    employee = request.user.employee_profile

    leaves = LeaveRequest.objects.filter(
        employee=employee
    ).order_by("-applied_on")

    serializer = LeaveRequestSerializer(leaves, many=True)

    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([IsEmployee])
@transaction.atomic
def cancel_leave(request, leave_id):

    employee = request.user.employee_profile

    try:
        # 🔒 Lock row to prevent race condition
        leave = (
            LeaveRequest.objects
            .select_for_update()
            .get(id=leave_id, employee=employee)
        )
    except LeaveRequest.DoesNotExist:
        return Response({"error": "Leave not found"}, status=404)

    # =========================================================
    # VALID STATUS CHECK
    # =========================================================
    if leave.status not in ["PENDING", "APPROVED"]:
        return Response(
            {"error": "Only pending or approved leave can be cancelled"},
            status=400
        )

    # =========================================================
    # 🔒 PAYROLL LOCK CHECK
    # =========================================================
    current = leave.start_date
    while current <= leave.end_date:
        if is_payroll_closed(current.year, current.month):
            return Response(
                {"error": "Cannot cancel leave for payroll closed month"},
                status=400
            )
        current += timedelta(days=1)

    # =========================================================
    # RESTORE LEAVE BALANCE (ONLY IF APPROVED + PAID)
    # =========================================================
    if leave.status == "APPROVED" and leave.leave_type.is_paid:

        days = leave.total_days()
        year = leave.start_date.year

        try:
            balance = (
                LeaveBalance.objects
                .select_for_update()
                .get(
                    employee=employee,
                    leave_type=leave.leave_type,
                    year=year
                )
            )

            balance.used -= days

            if balance.used < 0:
                balance.used = 0

            balance.save(update_fields=["used"])

        except LeaveBalance.DoesNotExist:
            pass  # Safety fallback

    # =========================================================
    # REMOVE AUTO-SYNCED ATTENDANCE (VERY IMPORTANT)
    # =========================================================
    if leave.status == "APPROVED":
        Attendance.objects.filter(
            employee=employee,
            date__range=[leave.start_date, leave.end_date],
            source="LEAVE_SYSTEM",
            locked=False
        ).delete()

    # =========================================================
    # UPDATE LEAVE STATUS
    # =========================================================
    leave.status = "CANCELLED"
    leave.save(update_fields=["status"])

    # =========================================================
    # LOG ACTION
    # =========================================================
    LeaveApprovalLog.objects.create(
        leave_request=leave,
        action="CANCELLED",
        performed_by=request.user
    )

    return Response({"message": "Leave cancelled successfully"})


@api_view(["POST"])
@permission_classes([IsHR])
@transaction.atomic
def reject_leave(request, leave_id):

    try:
        leave = (
            LeaveRequest.objects
            .select_for_update()
            .get(id=leave_id)
        )
    except LeaveRequest.DoesNotExist:
        return Response({"error": "Leave not found"}, status=404)

    if leave.status != "PENDING":
        return Response({"error": "Leave already processed"}, status=400)

    leave.status = "REJECTED"
    leave.rejected_on = timezone.now()
    leave.save(update_fields=["status", "rejected_on"])

    # Remove auto-created attendance
    Attendance.objects.filter(
        employee=leave.employee,
        date__range=[leave.start_date, leave.end_date],
        source="LEAVE_SYSTEM",
        locked=False
    ).delete()

    return Response({"message": "Leave rejected successfully"})