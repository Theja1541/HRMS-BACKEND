# apps/leaves/views.py

from django.utils import timezone
from django.db import transaction
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status

from apps.accounts.permissions import IsEmployee, IsHR
from apps.employees.models import Employee
from .models import LeaveRequest, LeaveBalance, LeaveType, LeaveApprovalLog
from .serializers import LeaveRequestSerializer, LeaveBalanceSerializer

from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from apps.accounts.permissions import IsEmployee, IsHR
from .models import LeaveType


# ======================================================
# APPLY LEAVE (Employee)
# ======================================================

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
        performed_by=employee
    )

    return Response({"message": "Leave applied successfully"})


@api_view(["POST"])
@permission_classes([IsHR])
@transaction.atomic
def approve_leave(request, leave_id):

    try:
        leave = LeaveRequest.objects.get(id=leave_id)
    except LeaveRequest.DoesNotExist:
        return Response({"error": "Leave not found"}, status=404)

    if leave.status != "PENDING":
        return Response({"error": "Leave already processed"}, status=400)

    days = leave.total_days()
    year = leave.start_date.year

    if leave.leave_type.is_paid:

        balance, created = LeaveBalance.objects.get_or_create(
            employee=leave.employee,
            leave_type=leave.leave_type,
            year=year,
            defaults={
                "total_allocated": leave.leave_type.annual_quota
            }
        )

        if balance.remaining < days:
            return Response(
                {"error": "Insufficient leave balance"},
                status=400
            )

        balance.used += days
        balance.save()

    leave.status = "APPROVED"
    leave.approved_by = request.user.employee_profile
    leave.approved_on = timezone.now()
    leave.save()

    LeaveApprovalLog.objects.create(
        leave_request=leave,
        action="APPROVED",
        performed_by=request.user.employee_profile
    )

    return Response({"message": "Leave approved successfully"})


@api_view(["POST"])
@permission_classes([IsHR])
def reject_leave(request, leave_id):

    try:
        leave = LeaveRequest.objects.get(id=leave_id)
    except LeaveRequest.DoesNotExist:
        return Response({"error": "Leave not found"}, status=404)

    if leave.status != "PENDING":
        return Response({"error": "Already processed"}, status=400)

    leave.status = "REJECTED"
    leave.save()

    LeaveApprovalLog.objects.create(
        leave_request=leave,
        action="REJECTED",
        performed_by=request.user.employee_profile
    )

    return Response({"message": "Leave rejected"})


@api_view(["GET"])
@permission_classes([IsEmployee])
def my_leave_balance(request):

    employee = request.user.employee_profile
    year = timezone.now().year

    balances = LeaveBalance.objects.filter(
        employee=employee,
        year=year
    )

    serializer = LeaveBalanceSerializer(balances, many=True)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsHR])
def all_leave_requests(request):

    leaves = LeaveRequest.objects.all().order_by("-applied_on")
    serializer = LeaveRequestSerializer(leaves, many=True)
    return Response(serializer.data)


# ==========================================
# GET ALL LEAVE TYPES
# ==========================================

@api_view(["GET"])
@permission_classes([IsEmployee | IsHR])
def leave_types(request):
    types = LeaveType.objects.filter(is_active=True)

    data = [
        {
            "id": t.id,
            "name": t.name,
            "annual_limit": t.annual_limit,
        }
        for t in types
    ]

    return Response(data)

# ======================================================
# EMPLOYEE: VIEW OWN LEAVE REQUESTS
# ======================================================

@api_view(["GET"])
@permission_classes([IsEmployee])
def my_leaves(request):

    employee = request.user.employee_profile

    leaves = LeaveRequest.objects.filter(
        employee=employee
    ).order_by("-applied_on")

    serializer = LeaveRequestSerializer(leaves, many=True)

    return Response(serializer.data)


# ======================================================
# EMPLOYEE: VIEW OWN LEAVE REQUESTS
# ======================================================

@api_view(["GET"])
@permission_classes([IsEmployee])
def my_leaves(request):

    employee = request.user.employee_profile

    leaves = LeaveRequest.objects.filter(
        employee=employee
    ).order_by("-applied_on")

    serializer = LeaveRequestSerializer(leaves, many=True)

    return Response(serializer.data)