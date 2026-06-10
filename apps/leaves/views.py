from django.utils import timezone
from django.db import transaction
from rest_framework import status
from apps.accounts.permissions import IsEmployee, IsHR
from apps.employees.models import Employee
from .models import LeaveRequest, LeaveBalance, LeaveType
from .serializers import LeaveRequestSerializer, LeaveBalanceSerializer
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from datetime import timedelta
from datetime import datetime
from django.db.models import Q
from apps.accounts.tenant_utils import get_current_company
from apps.payroll.utils import is_payroll_closed, is_super_admin
from .utils import sync_leave_to_attendance
from apps.attendance.models import Attendance
from apps.leaves.services.leave_service import LeaveService
from django.db.models import Count
from django.utils.timezone import now
from decimal import Decimal

def get_prorated_quota(employee, leave_type, year):
    # The admin requested that the assigned days strictly match the allocated days.
    # Therefore, we return the annual_quota without prorating to avoid confusion.
    quota = Decimal(str(leave_type.annual_quota))
    return quota.quantize(Decimal("0.01"))

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

    leave_type_qs = LeaveType.objects.filter(id=leave_type_id)
    try:
        leave_type = leave_type_qs.get()
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

    # Applicability Validation
    if leave_type.applicable_gender != "ALL" and employee.gender and leave_type.applicable_gender.upper() != employee.gender.upper():
        return Response({"error": f"This leave type is only applicable to {leave_type.applicable_gender.lower()} employees."}, status=400)

    if leave_type.applicable_employment_types and isinstance(leave_type.applicable_employment_types, list) and len(leave_type.applicable_employment_types) > 0:
        if employee.employment_type not in leave_type.applicable_employment_types:
            return Response({"error": "This leave type is not applicable to your employment type."}, status=400)

    if leave_type.applicable_departments and isinstance(leave_type.applicable_departments, list) and len(leave_type.applicable_departments) > 0:
        if employee.department not in leave_type.applicable_departments:
            return Response({"error": "This leave type is not applicable to your department."}, status=400)

    if leave_type.applicable_designations and isinstance(leave_type.applicable_designations, list) and len(leave_type.applicable_designations) > 0:
        if employee.designation not in leave_type.applicable_designations:
            return Response({"error": "This leave type is not applicable to your designation."}, status=400)

    # Advance Notice Validation
    if leave_type.advance_notice_days > 0:
        if (start_date - datetime.now().date()).days < leave_type.advance_notice_days:
            return Response({"error": f"You must apply at least {leave_type.advance_notice_days} days in advance for this leave type."}, status=400)

    # Probation Validation
    if not leave_type.allowed_during_probation and getattr(employee, "joining_date", None):
        if (datetime.now().date() - employee.joining_date).days < 180:
            return Response({"error": "This leave type is not allowed during your probation period."}, status=400)

    from apps.attendance.models import Holiday
    
    holiday_dates = set()
    if not leave_type.include_holidays:
        qs = Holiday.objects.filter(date__gte=start_date, date__lte=end_date)
        if getattr(employee, "company_id", None):
             qs = qs.filter(company_id=employee.company_id)
        holiday_dates = set(qs.values_list('date', flat=True))

    days = 0
    current_day = start_date
    while current_day <= end_date:
        is_weekend = current_day.weekday() in [5, 6]
        if not leave_type.include_weekends and is_weekend:
            current_day += timedelta(days=1)
            continue
            
        if not leave_type.include_holidays and current_day in holiday_dates:
            current_day += timedelta(days=1)
            continue
            
        days += 1
        current_day += timedelta(days=1)

    if days == 0:
        return Response({"error": "The selected date range does not contain any valid working days."}, status=400)

    if is_half_day:
        if days > 1:
            return Response(
                {"error": "Half day leave can only be for one day"},
                status=400
            )
        days = 0.5
        
    # Max Consecutive Days Validation
    if leave_type.max_consecutive_days and days > leave_type.max_consecutive_days:
        return Response({"error": f"You cannot apply for more than {leave_type.max_consecutive_days} consecutive days of this leave type."}, status=400)
        
    # Document Rules Validation
    if leave_type.document_required and leave_type.document_required_after_days > 0 and days > leave_type.document_required_after_days:
        if not request.data.get("document"):
             return Response({"error": f"Supporting document is required for leaves exceeding {leave_type.document_required_after_days} days."}, status=400)

    year = start_date.year

    if leave_type.is_paid:
        allocated_quota = get_prorated_quota(employee, leave_type, year)
        balance, _ = LeaveBalance.objects.select_for_update().get_or_create(
            employee=employee,
            leave_type=leave_type,
            year=year,
            defaults={
                "total_allocated": allocated_quota
            }
        )

        if balance.remaining < days:
            return Response(
                {"error": "Insufficient leave balance"},
                status=400
            )

    leave_kw = {
        "employee": employee,
        "leave_type": leave_type,
        "start_date": start_date,
        "end_date": end_date,
        "reason": reason,
        "is_half_day": is_half_day,
    }
    
    if "document" in request.FILES:
        leave_kw["document"] = request.FILES["document"]

    if getattr(employee, "company_id", None):
        leave_kw["company_id"] = employee.company_id
        
    leave = LeaveRequest.objects.create(**leave_kw)



    return Response({"message": "Leave applied successfully"})

@api_view(["POST"])
@permission_classes([IsHR])
@transaction.atomic
def approve_leave(request, leave_id):

    company = get_current_company(request)
    qs = LeaveRequest.objects.select_for_update()
    if company is not None:
        qs = qs.filter(employee__user__company=company)
    try:
        leave = qs.get(id=leave_id)
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
        allocated_quota = get_prorated_quota(leave.employee, leave.leave_type, year)
        balance, _ = LeaveBalance.objects.select_for_update().get_or_create(
            employee=leave.employee,
            leave_type=leave.leave_type,
            year=year,
            defaults={
                "total_allocated": allocated_quota,
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



    return Response({"message": "Leave approved successfully & attendance synced"})


@api_view(["GET"])
@permission_classes([IsEmployee])
def my_leave_balance(request):

    employee = request.user.employee_profile
    year = timezone.now().year

    # Get all active leave types (tenant-scoped)
    leave_types = LeaveType.objects.filter(is_active=True)
    if getattr(employee, "company_id", None):
        leave_types = leave_types.filter(company_id=employee.company_id)

    data = []
    for lt in leave_types:
        allocated_quota = get_prorated_quota(employee, lt, year)
        # Get or create balance record with updated quota
        balance, created = LeaveBalance.objects.get_or_create(
            employee=employee,
            leave_type=lt,
            year=year,
            defaults={
                "total_allocated": allocated_quota,
                "used": 0
            }
        )

        # Sync quota if admin changed it
        if balance.total_allocated != allocated_quota:
            balance.total_allocated = allocated_quota
            balance.save(update_fields=["total_allocated"])

        data.append({
            "leave_type": lt.name,
            "total_allocated": float(balance.total_allocated),
            "used": float(balance.used),
            "remaining": float(balance.total_allocated - balance.used),
        })

    return Response(data)


@api_view(["GET"])
@permission_classes([IsHR])
def all_leave_requests(request):
    company = get_current_company(request)
    status_filter = request.GET.get("status", None)

    leaves = LeaveRequest.objects.all().select_related("employee", "leave_type")
    if company is not None:
        leaves = leaves.filter(employee__user__company=company)

    if status_filter:
        leaves = leaves.filter(status=status_filter.upper())

    leaves = leaves.order_by("-applied_on")
    
    # Debug logging
    print(f"Total leaves found: {leaves.count()}")
    for leave in leaves:
        print(f"Leave ID: {leave.id}, Employee: {leave.employee.first_name} {leave.employee.last_name}, Status: {leave.status}")
    
    serializer = LeaveRequestSerializer(leaves, many=True, context={"request": request})
    print(f"Serialized data: {serializer.data}")
    return Response(serializer.data)

@api_view(["GET"])
@permission_classes([IsEmployee | IsHR])
def leave_types(request):
    company = get_current_company(request)
    types = LeaveType.objects.filter(is_active=True)

    data = [
    {
        "id": t.id,
        "name": t.name,
        "annual_quota": t.annual_quota,
        "is_paid": t.is_paid,
        "accrual_type": t.accrual_type,
        "carry_forward": t.carry_forward,
        "max_carry_forward": t.max_carry_forward,
        "encashable": t.encashable,
        "requires_approval": t.requires_approval,
        "allow_negative_balance": t.allow_negative_balance,
    }
    for t in types
]

    return Response(data)


@api_view(["GET", "POST"])
@permission_classes([IsHR])
def manage_leave_types(request):
    """
    GET: List all leave types (including inactive)
    POST: Create new leave type
    """
    company = get_current_company(request)
    if request.method == "GET":
        types = LeaveType.objects.all().order_by("-is_active", "name")
        data = [
            {
                "id": t.id,
                "name": t.name,
                "code": t.code,
                "annual_quota": t.annual_quota,
                "is_paid": t.is_paid,
                "accrual_type": t.accrual_type,
                "accrual_start_month": t.accrual_start_month,
                "carry_forward": t.carry_forward,
                "max_carry_forward": t.max_carry_forward,
                "encashable": t.encashable,
                "requires_approval": t.requires_approval,
                "allow_negative_balance": t.allow_negative_balance,
                "is_active": t.is_active,
                "is_system_leave": t.is_system_leave,
                "max_consecutive_days": t.max_consecutive_days,
                "advance_notice_days": t.advance_notice_days,
                "include_weekends": t.include_weekends,
                "include_holidays": t.include_holidays,
                "document_required": t.document_required,
                "document_required_after_days": t.document_required_after_days,
                "allowed_during_probation": t.allowed_during_probation,
                "prorate_for_new_joiners": t.prorate_for_new_joiners,
                "applicable_gender": t.applicable_gender,
                "applicable_employment_types": t.applicable_employment_types,
                "applicable_departments": t.applicable_departments,
                "applicable_designations": t.applicable_designations,
            }
            for t in types
        ]
        return Response(data)
    
    elif request.method == "POST":
        try:
            leave_type = LeaveType.objects.create(
                company=company,
                name=request.data.get("name"),
                code=request.data.get("code"),
                annual_quota=request.data.get("annual_quota", 0),
                is_paid=request.data.get("is_paid", True),
                accrual_type=request.data.get("accrual_type", "ANNUAL"),
                accrual_start_month=request.data.get("accrual_start_month", 1),
                carry_forward=request.data.get("carry_forward", False),
                max_carry_forward=request.data.get("max_carry_forward", 0),
                encashable=request.data.get("encashable", False),
                requires_approval=request.data.get("requires_approval", True),
                allow_negative_balance=request.data.get("allow_negative_balance", False),
                max_consecutive_days=request.data.get("max_consecutive_days"),
                advance_notice_days=request.data.get("advance_notice_days", 0),
                include_weekends=request.data.get("include_weekends", False),
                include_holidays=request.data.get("include_holidays", False),
                document_required=request.data.get("document_required", False),
                document_required_after_days=request.data.get("document_required_after_days", 0),
                allowed_during_probation=request.data.get("allowed_during_probation", True),
                prorate_for_new_joiners=request.data.get("prorate_for_new_joiners", True),
                applicable_gender=request.data.get("applicable_gender", "ALL"),
                applicable_employment_types=request.data.get("applicable_employment_types", []),
                applicable_departments=request.data.get("applicable_departments", []),
                applicable_designations=request.data.get("applicable_designations", []),
            )
            return Response(
                {"message": "Leave type created successfully", "id": leave_type.id},
                status=201
            )
        except Exception as e:
            return Response({"error": str(e)}, status=400)


@api_view(["PUT", "DELETE"])
@permission_classes([IsHR])
def update_leave_type(request, leave_type_id):
    """
    PUT: Update leave type
    DELETE: Deactivate leave type
    """
    company = get_current_company(request)
    qs = LeaveType.objects.filter(id=leave_type_id)
    try:
        leave_type = qs.get()
    except LeaveType.DoesNotExist:
        return Response({"error": "Leave type not found"}, status=404)
    
    if request.method == "PUT":
        leave_type.name = request.data.get("name", leave_type.name)
        leave_type.code = request.data.get("code", leave_type.code)
        leave_type.annual_quota = request.data.get("annual_quota", leave_type.annual_quota)
        leave_type.is_paid = request.data.get("is_paid", leave_type.is_paid)
        leave_type.accrual_type = request.data.get("accrual_type", leave_type.accrual_type)
        leave_type.accrual_start_month = request.data.get("accrual_start_month", leave_type.accrual_start_month)
        leave_type.carry_forward = request.data.get("carry_forward", leave_type.carry_forward)
        leave_type.max_carry_forward = request.data.get("max_carry_forward", leave_type.max_carry_forward)
        leave_type.encashable = request.data.get("encashable", leave_type.encashable)
        leave_type.requires_approval = request.data.get("requires_approval", leave_type.requires_approval)
        leave_type.allow_negative_balance = request.data.get("allow_negative_balance", leave_type.allow_negative_balance)
        leave_type.is_active = request.data.get("is_active", leave_type.is_active)
        
        # New fields
        if "max_consecutive_days" in request.data:
            leave_type.max_consecutive_days = request.data.get("max_consecutive_days")
        if "advance_notice_days" in request.data:
            leave_type.advance_notice_days = request.data.get("advance_notice_days")
        if "include_weekends" in request.data:
            leave_type.include_weekends = request.data.get("include_weekends")
        if "include_holidays" in request.data:
            leave_type.include_holidays = request.data.get("include_holidays")
        if "document_required" in request.data:
            leave_type.document_required = request.data.get("document_required")
        if "document_required_after_days" in request.data:
            leave_type.document_required_after_days = request.data.get("document_required_after_days")
        if "allowed_during_probation" in request.data:
            leave_type.allowed_during_probation = request.data.get("allowed_during_probation")
        if "prorate_for_new_joiners" in request.data:
            leave_type.prorate_for_new_joiners = request.data.get("prorate_for_new_joiners")
        if "applicable_gender" in request.data:
            leave_type.applicable_gender = request.data.get("applicable_gender")
        if "applicable_employment_types" in request.data:
            leave_type.applicable_employment_types = request.data.get("applicable_employment_types")
        if "applicable_departments" in request.data:
            leave_type.applicable_departments = request.data.get("applicable_departments")
        if "applicable_designations" in request.data:
            leave_type.applicable_designations = request.data.get("applicable_designations")

        try:
            leave_type.save()
            return Response({"message": "Leave type updated successfully"})
        except Exception as e:
            return Response({"error": str(e)}, status=400)
    
    elif request.method == "DELETE":
        leave_type.is_active = False
        leave_type.save()
        return Response({"message": "Leave type deactivated successfully"})

@api_view(["GET"])
@permission_classes([IsEmployee])
def my_leaves(request):

    employee = request.user.employee_profile

    leaves = LeaveRequest.objects.filter(
        employee=employee
    ).order_by("-applied_on")

    serializer = LeaveRequestSerializer(leaves, many=True, context={"request": request})

    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsEmployee])
def leave_detail(request, leave_id):

    employee = request.user.employee_profile

    try:
        leave = LeaveRequest.objects.get(id=leave_id, employee=employee)
    except LeaveRequest.DoesNotExist:
        return Response({"error": "Leave not found"}, status=404)

    serializer = LeaveRequestSerializer(leave, context={"request": request})
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
    leave.save(update_fields=["status"])



    return Response({"message": "Leave rejected successfully"})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def leave_dashboard(request):

    today = now().date()

    total_requests = LeaveRequest.objects.count()

    pending_requests = LeaveRequest.objects.filter(
        status="PENDING"
    ).count()

    approved_requests = LeaveRequest.objects.filter(
        status="APPROVED"
    ).count()

    rejected_requests = LeaveRequest.objects.filter(
        status="REJECTED"
    ).count()

    today_leaves = LeaveRequest.objects.filter(
        start_date__lte=today,
        end_date__gte=today,
        status="APPROVED"
    ).values(
        "employee__first_name",
        "employee__last_name",
        "leave_type__name",
        "start_date",
        "end_date"
    )

    recent_requests = LeaveRequest.objects.order_by(
        "-applied_on"
    )[:5].values(
        "employee__first_name",
        "employee__last_name",
        "leave_type__name",
        "status",
        "start_date"
    )

    return Response({
        "total_requests": total_requests,
        "pending_requests": pending_requests,
        "approved_requests": approved_requests,
        "rejected_requests": rejected_requests,
        "today_leaves": list(today_leaves),
        "recent_requests": list(recent_requests)
    })


from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import LeaveRequest


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def leave_calendar(request):

    employee_id = request.GET.get("employee_id")
    department = request.GET.get("department")
    leave_type = request.GET.get("leave_type")

    # Base query
    leaves = LeaveRequest.objects.filter(status="APPROVED").select_related(
        "employee", "leave_type"
    )

    # ⭐ Employee filter
    if employee_id and employee_id != "":
        leaves = leaves.filter(employee__id=int(employee_id))
        
    if department and department != "":
        leaves = leaves.filter(employee__department=department)
        
    if leave_type and leave_type != "":
        leaves = leaves.filter(leave_type__name=leave_type)

    events = []

    for leave in leaves:

        avatar = None
        if leave.employee.profile_photo:
            avatar = request.build_absolute_uri(
                leave.employee.profile_photo.url
            )
            
        document = None
        if leave.document:
            document = request.build_absolute_uri(leave.document.url)

        events.append({
            "type": "leave",
            "title": f"{leave.employee.first_name} {leave.employee.last_name}",
            "start": leave.start_date,
            "end": leave.end_date,
            "leave_type": leave.leave_type.name,
            "avatar": avatar,
            "department": leave.employee.department,
            "document": document
        })

    return Response(events)

@api_view(["PUT"])
def update_leave_dates(request):

    employee = request.data.get("employee")
    start = request.data.get("start_date")
    end = request.data.get("end_date")

    leave = LeaveRequest.objects.filter(
        employee__first_name__icontains=employee
    ).first()

    leave.start_date = start
    leave.end_date = end
    leave.save()

    return Response({"status":"updated"})


@api_view(["GET"])
def debug_leaves(request):
    """Debug endpoint to check leave data"""
    from django.forms.models import model_to_dict
    
    all_leaves = LeaveRequest.objects.all()
    pending_leaves = LeaveRequest.objects.filter(status="PENDING")
    
    data = {
        "total_leaves": all_leaves.count(),
        "pending_leaves": pending_leaves.count(),
        "leaves": []
    }
    
    for leave in all_leaves[:10]:
        data["leaves"].append({
            "id": leave.id,
            "employee": f"{leave.employee.first_name} {leave.employee.last_name}",
            "employee_id": leave.employee.employee_id,
            "leave_type": leave.leave_type.name,
            "status": leave.status,
            "start_date": str(leave.start_date),
            "end_date": str(leave.end_date),
            "reason": leave.reason,
            "applied_on": str(leave.applied_on)
        })
    
    return Response(data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def leave_analytics(request):
    """
    Returns highly optimized, tenant-isolated count of:
      - pending_leaves: Leave requests pending approval.
      - on_leave_today: Active approved leaves for today.
    """
    company = get_current_company(request)
    today = timezone.now().date()

    pending_qs = LeaveRequest.objects.filter(status="PENDING")
    approved_today_qs = LeaveRequest.objects.filter(
        status="APPROVED",
        start_date__lte=today,
        end_date__gte=today
    )

    if company is not None:
        pending_qs = pending_qs.filter(employee__user__company=company)
        approved_today_qs = approved_today_qs.filter(employee__user__company=company)

    pending_leaves = pending_qs.count()
    on_leave_today = approved_today_qs.count()

    return Response({
        "pending_leaves": pending_leaves,
        "on_leave_today": on_leave_today
    })