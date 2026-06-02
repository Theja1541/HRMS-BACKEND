from datetime import date, datetime
from calendar import monthrange
import re
from collections import defaultdict
from django.utils import timezone
from django.db.models import Count, Q
from django.core.exceptions import ValidationError
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from .models import Attendance
from apps.holidays.models import Holiday
from .constants import ATTENDANCE_STATUS_CHOICES
from .serializers import AttendanceSerializer
from apps.accounts.permissions import IsEmployee, IsHR, check_company_module_permission
from apps.employees.models import Employee
from openpyxl import Workbook
from openpyxl.styles import Font
from django.http import HttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from .tasks import send_monthly_attendance_manual
from datetime import date, datetime
import calendar
from django.utils import timezone
# from apps.attendance.models import WeekendPolicy
from apps.attendance.models import WorkCalendar
import calendar
from datetime import timedelta
from django.utils import timezone
from datetime import datetime, timedelta
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from apps.accounts.permissions import IsHR
from apps.attendance.models import Attendance
from apps.employees.models import Employee
from datetime import date
import calendar
from django.utils import timezone
from apps.attendance.models import Attendance
from apps.holidays.models import Holiday
from apps.employees.models import Employee
from apps.leaves.models import LeaveRequest
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from apps.accounts.permissions import IsHR
from apps.attendance.utils import is_payroll_closed
from apps.accounts.tenant_utils import get_current_company
from apps.payroll.utils.payroll_helpers import (
    is_payroll_closed,
    is_super_admin,
)

# ============================================================
# COMMON UTIL
# ============================================================

def validate_month_format(month: str):
    if not re.match(r"^\d{4}-\d{2}$", month):
        raise ValidationError("Invalid month format. Use YYYY-MM.")


def is_second_or_fourth_saturday(date_obj):
    if date_obj.weekday() != 5:
        return False

    week_number = (date_obj.day - 1) // 7 + 1
    return week_number in [2, 4]


def calculate_working_days(year, month, employee=None):

    today = timezone.now().date()

    last_day = date(year, month, calendar.monthrange(year, month)[1])

    holidays = Holiday.objects.filter(
        from_date__year__lte=year,
        to_date__year__gte=year,
        from_date__month__lte=month,
        to_date__month__gte=month,
        is_active=True
    )
    
    holiday_dates = set()
    for h in holidays:
        current = h.from_date
        while current <= h.to_date:
            if current.year == year and current.month == month:
                holiday_dates.add(current)
            current += timedelta(days=1)

    working_days = 0
    holiday_count = len(holiday_dates)
    days_in_month = last_day.day

    for day in range(1, days_in_month + 1):
        current_date = date(year, month, day)

        # Skip future dates
        if current_date > today:
            continue

        # Skip before joining
        if employee and employee.joining_date:
            if current_date < employee.joining_date:
                continue

        # Weekend logic
        if employee and employee.work_calendar:
            weekend_days = employee.work_calendar.weekend_days
        else:
            weekend_days = [6]  # Default Sunday

        if current_date.weekday() in weekend_days:
            continue

        # Holiday
        if current_date in holiday_dates:
            continue

        working_days += 1

    return working_days, holiday_count, days_in_month


# ============================================================
# EMPLOYEE CHECK-IN
# ============================================================

@api_view(["POST"])
@permission_classes([IsEmployee])
def check_in(request):
    employee = request.user.employee_profile
    today = date.today()

    if is_payroll_closed(today.year, today.month) and not is_super_admin(request.user):
        return Response(
            {"error": "Payroll month is CLOSED. Check-in not allowed."},
            status=status.HTTP_400_BAD_REQUEST
            )

    defaults = {"status": "PRESENT"}
    if getattr(employee, "company_id", None):
        defaults["company_id"] = employee.company_id
    attendance, created = Attendance.objects.get_or_create(
        employee=employee,
        date=today,
        defaults=defaults
    )

    if attendance.check_in:
        return Response(
            {"error": "Already checked in"},
            status=status.HTTP_400_BAD_REQUEST
        )

    attendance.check_in = timezone.now()
    attendance.status = "PRESENT"
    attendance.save()
    

    return Response(
        {
            "message": "Check-in successful",
            "check_in_time": attendance.check_in
        },
        status=status.HTTP_200_OK
    )


# ============================================================
# EMPLOYEE CHECK-OUT
# ============================================================

@api_view(["POST"])
@permission_classes([IsEmployee])
def check_out(request):
    employee = request.user.employee_profile
    today = date.today()

    if is_payroll_closed(today.year, today.month) and not is_super_admin(request.user):
        return Response(
            {"error": "Payroll month is CLOSED. Check-out not allowed."},
            status=status.HTTP_400_BAD_REQUEST
            )

    try:
        attendance = Attendance.objects.get(
            employee=employee,
            date=today
        )
    except Attendance.DoesNotExist:
        return Response(
            {"error": "Check-in required first"},
            status=status.HTTP_400_BAD_REQUEST
        )

    if attendance.check_out:
        return Response(
            {"error": "Already checked out"},
            status=status.HTTP_400_BAD_REQUEST
        )

    attendance.check_out = timezone.now()

    # Optional: calculate work hours
    if attendance.check_in:
        duration = attendance.check_out - attendance.check_in
        attendance.work_hours = round(duration.total_seconds() / 3600, 2)

    attendance.save()

    return Response(
        {
            "message": "Check-out successful",
            "check_out_time": attendance.check_out
        },
        status=status.HTTP_200_OK
    )


# ============================================================
# EMPLOYEE: VIEW OWN MONTHLY ATTENDANCE
# ============================================================

@api_view(["GET"])
@permission_classes([IsEmployee])
def my_attendance(request):
    employee = request.user.employee_profile
    month = request.query_params.get("month")

    if not month:
        return Response(
            {"error": "Month required (YYYY-MM)"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        validate_month_format(month)
        year, month_num = map(int, month.split("-"))
    except (ValueError, ValidationError):
        return Response(
            {"error": "Invalid month format. Use YYYY-MM"},
            status=status.HTTP_400_BAD_REQUEST
        )

    records = Attendance.objects.filter(
        employee=employee,
        date__year=year,
        date__month=month_num
    ).order_by("date")

    serialized_records = AttendanceSerializer(records, many=True).data

    working_days, holiday_count, days_in_month = calculate_working_days(
    year, month_num, employee=employee)

    # ---------------------------------------------------------
    # AGGREGATE SUMMARY (Enterprise Payroll Ready)
    # ---------------------------------------------------------

    summary = records.aggregate(
        present=Count("id", filter=Q(status="PRESENT")),
        half_day=Count("id", filter=Q(status="HALF_DAY")),
        paid_leave=Count("id", filter=Q(status="PAID_LEAVE")),
        unpaid_leave=Count("id", filter=Q(status="UNPAID_LEAVE")),
        absent=Count("id", filter=Q(status="ABSENT")),
        holiday=Count("id", filter=Q(status="HOLIDAY")),
        # late=Count("id", filter=Q(status="LATE")),
        # late_days = records.filter(is_late=True).count()
        late=Count("id", filter=Q(is_late=True)), 
    )

    present_days = summary["present"] or 0
    half_days = summary["half_day"] or 0
    paid_leave_days = summary["paid_leave"] or 0
    unpaid_leave_days = summary["unpaid_leave"] or 0
    absent_days = summary["absent"] or 0
    holiday_days = summary["holiday"] or 0
    late_days = summary["late"] or 0

    # ---------------------------------------------------------
    # PAYABLE DAYS
    # ---------------------------------------------------------

    payable_days = (
        present_days
        + (half_days * 0.5)
        + paid_leave_days
    )

    deductible_days = (
        unpaid_leave_days
        + absent_days
    )

    attendance_percentage = 0

    if working_days > 0:
        attendance_percentage = round(
            (payable_days / working_days) * 100,
            2
        )

    return Response({
    "month": month,
    "summary": {
        "total_days_in_month": days_in_month,
        "working_days": working_days,
        "holiday": holiday_days,
        "present": present_days,
        "half_day": half_days,
        "paid_leave": paid_leave_days,
        "unpaid_leave": unpaid_leave_days,
        "absent": absent_days,
        "late": late_days,
        "payable_days": payable_days,
        "deductible_days": deductible_days,
        "attendance_percentage": attendance_percentage,
    },
    "records": serialized_records
})


# ============================================================
# HR: GROUPED ATTENDANCE LIST
# ============================================================

@api_view(["GET"])
@permission_classes([IsHR])
def attendance_list(request):
    records = Attendance.objects.select_related("employee").all()

    grouped = defaultdict(dict)

    for record in records:
        date_str = str(record.date)

        grouped[date_str][record.employee.id] = {
            "id": record.id,
            "status": record.status,
            "check_in": record.check_in,
            "check_out": record.check_out,
            "work_hours": record.work_hours,
        }

    return Response(grouped)


# ============================================================
# HR: MONTHLY REPORT
# ============================================================

@api_view(["GET"])
@permission_classes([IsHR])
def monthly_report(request):
    month = request.query_params.get("month")

    if not month:
        return Response(
            {"error": "month query param required (YYYY-MM)"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        validate_month_format(month)
        year, month_num = map(int, month.split("-"))
    except (ValueError, ValidationError):
        return Response(
            {"error": "Invalid month format. Use YYYY-MM"},
            status=status.HTTP_400_BAD_REQUEST
        )

    records = Attendance.objects.filter(
        date__year=year,
        date__month=month_num
    )
    company = get_current_company(request)
    if company is not None:
        records = records.filter(company=company)

    serializer = AttendanceSerializer(records, many=True)
    return Response(serializer.data)


def calculate_attendance_status(employee, check_in_time):

    # If employee works from home
    if employee.is_work_from_home:
        return {
            "status": "PRESENT",
            "is_late": False,
            "is_half_day": False,
            "attendance_type": "WFH"
        }

    shift = employee.shift

    if not shift:
        # No shift assigned → default present
        return {
            "status": "PRESENT",
            "is_late": False,
            "is_half_day": False,
            "attendance_type": "OFFICE"
        }

    shift_start = datetime.combine(
        timezone.now().date(),
        shift.start_time
    )

    grace_limit = shift_start + timedelta(minutes=shift.grace_minutes)
    half_day_limit = shift_start + timedelta(hours=3)

    check_in_datetime = datetime.combine(
        timezone.now().date(),
        check_in_time
    )

    if check_in_datetime <= grace_limit:
        return {
            "status": "PRESENT",
            "is_late": False,
            "is_half_day": False,
            "attendance_type": "OFFICE"
        }

    elif check_in_datetime <= half_day_limit:
        return {
            "status": "PRESENT",
            "is_late": True,
            "is_half_day": False,
            "attendance_type": "OFFICE"
        }

    else:
        return {
            "status": "HALF_DAY",
            "is_late": True,
            "is_half_day": True,
            "attendance_type": "OFFICE"
        }
    
# ============================================================
# HR: MARK SINGLE ATTENDANCE
# ============================================================

@api_view(["POST"])
@permission_classes([IsHR])
def mark_attendance(request):
    if not check_company_module_permission(request, "attendance", "edit", page_name="attendance"):
        return Response({"error": "Edit action is disabled in Attendance for this company."}, status=status.HTTP_403_FORBIDDEN)

    employee_id = request.data.get("employee_id")
    date_value = request.data.get("date")  # YYYY-MM-DD
    status_value = request.data.get("status")  # PRESENT / ABSENT / LEAVE etc.
    check_in_value = request.data.get("check_in")  # Optional (ISO format)
    edit_reason = request.data.get("edit_reason") or ""  # Optional; default used when updating

    # ============================
    # VALIDATION
    # ============================

    if not employee_id or not date_value or not status_value:
        return Response(
            {"error": "employee_id, date and status are required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    valid_statuses = [choice[0] for choice in ATTENDANCE_STATUS_CHOICES]

    if status_value.upper() not in valid_statuses:
        return Response(
            {"error": "Invalid status value"},
            status=status.HTTP_400_BAD_REQUEST
        )

    company = get_current_company(request)
    qs = Employee.objects.filter(id=employee_id)
    if company is not None:
        qs = qs.filter(user__company=company)
    try:
        employee = qs.get()
    except Employee.DoesNotExist:
        return Response(
            {"error": "Employee not found"},
            status=status.HTTP_404_NOT_FOUND
        )

    try:
        parsed_date = datetime.strptime(date_value, "%Y-%m-%d").date()
        if is_payroll_closed(parsed_date.year, parsed_date.month):
            return Response(
                {"error": "Payroll month is CLOSED. Attendance cannot be modified."},
                status=status.HTTP_400_BAD_REQUEST
                )
    except ValueError:
        return Response(
            {"error": "Invalid date format. Use YYYY-MM-DD"},
            status=status.HTTP_400_BAD_REQUEST
        )

    # ============================
    # HOLIDAY CHECK
    # ============================
    from apps.attendance.utils import is_holiday
    is_hol, hol_obj = is_holiday(parsed_date, company=company)
    
    if is_hol and status_value.upper() == "ABSENT":
        return Response(
            {"error": f"Cannot mark absent on a holiday ({hol_obj.holiday_name})"},
            status=status.HTTP_400_BAD_REQUEST
        )

    # ============================
    # CREATE OR UPDATE ATTENDANCE
    # ============================

    defaults = {}
    if getattr(employee, "company_id", None):
        defaults["company_id"] = employee.company_id
    attendance, created = Attendance.objects.get_or_create(
        employee=employee,
        date=parsed_date,
        defaults=defaults
    )

    # Store previous status for edit tracking
    previous_status = attendance.status if not created else None

    attendance.status = status_value.upper()

    # Track edit (only when updating existing record)
    if not created:
        attendance.is_edited = True
        attendance.edit_reason = edit_reason.strip() or "Updated from Daily Attendance"
        attendance.edited_by = request.user
        attendance.edited_at = timezone.now()
        attendance.previous_status = previous_status

    # Reset late data
    attendance.is_late = False
    attendance.late_minutes = 0

    # ============================
    # CHECK-IN BASED LOGIC
    # ============================

    if check_in_value:
        try:
            check_in_datetime = datetime.fromisoformat(check_in_value)
            if timezone.is_naive(check_in_datetime):
                check_in_datetime = timezone.make_aware(check_in_datetime)

            attendance.check_in = check_in_datetime

        except Exception:
            return Response(
                {"error": "Invalid check_in datetime format"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Only calculate late if marked PRESENT
        if attendance.status == "PRESENT":

            # Work From Home employees
            if employee.is_work_from_home:
                attendance.attendance_type = "WFH"
                attendance.is_late = False
                attendance.late_minutes = 0

            else:
                shift = employee.shift

                if shift:
                    shift_start_datetime = check_in_datetime.replace(
                        hour=shift.start_time.hour,
                        minute=shift.start_time.minute,
                        second=0,
                        microsecond=0,
                    )

                    grace_limit = shift_start_datetime + timedelta(
                        minutes=shift.grace_minutes
                    )

                    if check_in_datetime > grace_limit:
                        late_delta = check_in_datetime - shift_start_datetime
                        late_minutes = int(late_delta.total_seconds() // 60)

                        attendance.is_late = True
                        attendance.late_minutes = late_minutes
                    else:
                        attendance.is_late = False
                        attendance.late_minutes = 0

                attendance.attendance_type = "OFFICE"

    # ============================
    # SAVE
    # ============================

    attendance.save()

    return Response(
        {
            "message": "Attendance marked successfully",
            "is_late": attendance.is_late,
            "late_minutes": attendance.late_minutes
        },
        status=status.HTTP_200_OK
    )


# ============================================================
# HR: BULK MARK ATTENDANCE (Optimized)
# ============================================================

@api_view(["POST"])
@permission_classes([IsHR])
def bulk_mark_attendance(request):
    if not check_company_module_permission(request, "attendance", "edit", page_name="attendance"):
        return Response({"error": "Edit action is disabled in Attendance for this company."}, status=status.HTTP_403_FORBIDDEN)

    date_value = request.data.get("date")
    status_value = request.data.get("status")
    edit_reason = request.data.get("edit_reason") or "Bulk applied from Daily Attendance"

    if not date_value or not status_value:
        return Response(
            {"error": "date and status required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    valid_statuses = [choice[0] for choice in ATTENDANCE_STATUS_CHOICES]

    if status_value.upper() not in valid_statuses:
        return Response(
            {"error": "Invalid status value"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        parsed_date = datetime.strptime(date_value, "%Y-%m-%d").date()
        if is_payroll_closed(parsed_date.year, parsed_date.month):
            return Response(
                {"error": "Payroll month is CLOSED. Bulk attendance not allowed."},
                status=status.HTTP_400_BAD_REQUEST
                )
    except ValueError:
        return Response(
            {"error": "Invalid date format. Use YYYY-MM-DD"},
            status=status.HTTP_400_BAD_REQUEST
        )

    company = get_current_company(request)
    
    # ============================
    # HOLIDAY CHECK
    # ============================
    from apps.attendance.utils import is_holiday
    is_hol, hol_obj = is_holiday(parsed_date, company=company)
    
    if is_hol and status_value.upper() == "ABSENT":
        return Response(
            {"error": f"Cannot bulk mark absent on a holiday ({hol_obj.holiday_name})"},
            status=status.HTTP_400_BAD_REQUEST
        )

    company = get_current_company(request)
    employees = Employee.objects.filter(is_active=True)
    if company is not None:
        employees = employees.filter(user__company=company)

    updated_count = 0
    created_count = 0

    for emp in employees:
        defaults = {"status": status_value.upper()}
        if getattr(emp, "company_id", None):
            defaults["company_id"] = emp.company_id
        attendance, created = Attendance.objects.get_or_create(
            employee=emp,
            date=parsed_date,
            defaults=defaults
        )

        if not created:
            attendance.previous_status = attendance.status
            attendance.status = status_value.upper()
            attendance.is_edited = True
            attendance.edit_reason = (edit_reason or "Bulk applied from Daily Attendance").strip()
            attendance.edited_by = request.user
            attendance.edited_at = timezone.now()
            attendance.save()
            updated_count += 1
        else:
            created_count += 1

    return Response(
        {
            "message": "Bulk attendance marked successfully",
            "created": created_count,
            "updated": updated_count
        },
        status=status.HTTP_200_OK
    )


# ============================================================
# SUPER ADMIN: UNLOCK ATTENDANCE
# ============================================================

@api_view(["POST"])
@permission_classes([IsAdminUser])
def unlock_attendance(request):
    employee_id = request.data.get("employee_id")
    date_value = request.data.get("date")

    if not employee_id or not date_value:
        return Response(
            {"error": "employee_id and date required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        attendance = Attendance.objects.get(
            employee__id=employee_id,
            date=date_value
        )
    except Attendance.DoesNotExist:
        return Response(
            {"error": "Attendance not found"},
            status=status.HTTP_404_NOT_FOUND
        )

    attendance.manually_unlocked = True
    attendance.save()

    return Response(
        {"message": "Attendance unlocked successfully"},
        status=status.HTTP_200_OK
    )


@api_view(["GET"])
@permission_classes([IsEmployee])
def export_my_attendance(request):
    employee = request.user.employee_profile
    month = request.query_params.get("month")

    if not month:
        return Response(
            {"error": "Month required (YYYY-MM)"},
            status=status.HTTP_400_BAD_REQUEST
        )

    year, month_num = map(int, month.split("-"))

    records = Attendance.objects.filter(
        employee=employee,
        date__year=year,
        date__month=month_num
    ).order_by("date")

    # Create workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Attendance"

    # Header
    headers = [
        "Date",
        "Status",
        "Check In",
        "Check Out",
        "Late Minutes",
        "Work Hours",
        "Notes",
    ]

    ws.append(headers)

    # Make header bold
    for col in range(1, len(headers) + 1):
        ws.cell(row=1, column=col).font = Font(bold=True)

    # Add records
    for record in records:
        ws.append([
            record.date.strftime("%Y-%m-%d"),
            record.status,
            record.check_in.strftime("%H:%M:%S") if record.check_in else "",
            record.check_out.strftime("%H:%M:%S") if record.check_out else "",
            record.late_minutes,
            record.work_hours,
            record.notes or "",
        ])

    # Auto column width
    for column_cells in ws.columns:
        length = max(len(str(cell.value)) if cell.value else 0 for cell in column_cells)
        ws.column_dimensions[column_cells[0].column_letter].width = length + 2

    # Prepare response
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = f'attachment; filename="Attendance_{month}.xlsx"'

    wb.save(response)

    return response


@api_view(["POST"])
@permission_classes([IsAdminUser])
def send_attendance_now(request):
    if not check_company_module_permission(request, "attendance", "create", page_name="attendance"):
        return Response({"error": "Create/Send action is disabled in Attendance for this company."}, status=status.HTTP_403_FORBIDDEN)

    year = request.data.get("year")
    month = request.data.get("month")

    if not year or not month:
        return Response({"error": "Year and month required"}, status=400)

    send_monthly_attendance_manual.delay(year, month)

    return Response({"message": "Attendance emails triggered successfully"})



@api_view(["POST"])
@permission_classes([IsHR])
def generate_today_attendance(request):
    if not check_company_module_permission(request, "attendance", "create", page_name="attendance"):
        return Response({"error": "Create action is disabled in Attendance for this company."}, status=status.HTTP_403_FORBIDDEN)

    today = timezone.now().date()
    if is_payroll_closed(today.year, today.month) and not is_super_admin(request.user):
        return Response(
            {"error": "Payroll month is CLOSED. Cannot generate attendance."},
            status=status.HTTP_400_BAD_REQUEST
            )
    created_count = 0

    employees = Employee.objects.filter(is_active=True)

    with transaction.atomic():

        for employee in employees:

            # Skip if already exists
            if Attendance.objects.filter(employee=employee, date=today).exists():
                continue

            # 1️⃣ Holiday
            if Holiday.objects.filter(from_date__lte=today, to_date__gte=today, is_active=True).exists():
                Attendance.objects.create(
                    employee=employee,
                    date=today,
                    status="HOLIDAY"
                )
                created_count += 1
                continue

            # 2️⃣ Weekend (basic Sunday logic)
            weekend_days = [6]  # Sunday
            if employee.work_calendar:
                weekend_days = employee.work_calendar.weekend_days

            if today.weekday() in weekend_days:
                Attendance.objects.create(
                    employee=employee,
                    date=today,
                    # status="HOLIDAY"
                    status="WEEK_OFF"
                )
                created_count += 1
                continue

            # 3️⃣ Approved Leave
            leave = LeaveRequest.objects.filter(
                employee=employee,
                start_date__lte=today,
                end_date__gte=today,
                status="APPROVED"
            ).select_related("leave_type").first()

            if leave:
                Attendance.objects.create(
                    employee=employee,
                    date=today,
                    status="PAID_LEAVE" if leave.leave_type.is_paid else "UNPAID_LEAVE"
                )
                created_count += 1
                continue

            # 4️⃣ Otherwise mark ABSENT
            Attendance.objects.create(
                employee=employee,
                date=today,
                status="ABSENT"
            )
            created_count += 1

    return Response(
        {
            "message": "Daily attendance generated successfully",
            "records_created": created_count
        },
        status=status.HTTP_200_OK
    )


@api_view(["GET"])
@permission_classes([IsHR])
def edited_attendance_history(request):
    """Get all edited attendance records for a specific month"""
    month = request.query_params.get("month")

    if not month:
        return Response(
            {"error": "month query param required (YYYY-MM)"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        validate_month_format(month)
        year, month_num = map(int, month.split("-"))
    except (ValueError, ValidationError):
        return Response(
            {"error": "Invalid month format. Use YYYY-MM"},
            status=status.HTTP_400_BAD_REQUEST
        )

    edited_records = Attendance.objects.filter(
        date__year=year,
        date__month=month_num,
        is_edited=True
    ).select_related("employee", "edited_by").order_by("-edited_at")

    data = []
    for record in edited_records:
        # Get edited_by name
        if record.edited_by:
            edited_by_name = f"{record.edited_by.first_name} {record.edited_by.last_name}".strip()
            if not edited_by_name:
                edited_by_name = record.edited_by.username
        else:
            edited_by_name = "System"

        data.append({
            "id": record.id,
            "employee_name": f"{record.employee.first_name} {record.employee.last_name}",
            "employee_id": record.employee.employee_id,
            "date": record.date,
            "previous_status": record.previous_status,
            "updated_status": record.status,
            "edited_by": edited_by_name,
            "edit_reason": record.edit_reason,
            "edited_at": record.edited_at,
        })

    return Response(data, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsHR])
def dashboard_summary(request):
    from datetime import timedelta
    from django.utils import timezone
    from django.db.models import Count, Q
    from apps.employees.models import Employee
    from apps.attendance.models import Attendance
    from apps.accounts.tenant_utils import get_current_company
    
    company = get_current_company(request)
    today = timezone.localdate()
    
    # Total active employees
    employee_qs = Employee.objects.filter(user__is_active=True)
    if company is not None:
        employee_qs = employee_qs.filter(user__company=company)
    total_employees = employee_qs.count()
    
    # Today's attendance
    today_attendance = Attendance.objects.filter(date=today)
    if company is not None:
        today_attendance = today_attendance.filter(employee__user__company=company)
    
    present_today = today_attendance.filter(status="PRESENT").count()
    absent_today = today_attendance.filter(status="ABSENT").count()
    late_today = today_attendance.filter(is_late=True).count()
    wfh_today = today_attendance.filter(attendance_type="WFH").count()
    
    attendance_percentage = 0
    if total_employees > 0:
        attendance_percentage = round((present_today / total_employees) * 100, 1)

    # Weekly trend
    last_7_days = [today - timedelta(days=i) for i in range(6, -1, -1)]
    trend_data = []
    
    weekly_attendance = Attendance.objects.filter(date__in=last_7_days)
    if company is not None:
        weekly_attendance = weekly_attendance.filter(employee__user__company=company)
        
    weekly_attendance_summary = weekly_attendance.values('date').annotate(
        present=Count('id', filter=Q(status='PRESENT')),
        absent=Count('id', filter=Q(status='ABSENT'))
    )
    
    trend_dict = {item['date'].strftime('%Y-%m-%d'): item for item in weekly_attendance_summary}
    
    for d in last_7_days:
        date_str = d.strftime('%Y-%m-%d')
        data = trend_dict.get(date_str, {'present': 0, 'absent': 0})
        trend_data.append({
            "name": d.strftime('%a'), # Short day name like Mon, Tue
            "date": date_str,
            "present": data['present'],
            "absent": data['absent']
        })

    return Response({
        "present_today": present_today,
        "absent_today": absent_today,
        "late_today": late_today,
        "wfh_today": wfh_today,
        "attendance_percentage": attendance_percentage,
        "total_employees": total_employees,
        "weekly_trend": trend_data
    })


@api_view(["GET"])
@permission_classes([IsHR | IsEmployee])
def attendance_day_status(request):
    """
    Returns holiday and week off status for a given date.
    """
    from datetime import datetime
    date_str = request.query_params.get("date")
    if not date_str:
        return Response({"error": "date parameter required (YYYY-MM-DD)"}, status=status.HTTP_400_BAD_REQUEST)
        
    try:
        parsed_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return Response({"error": "Invalid date format"}, status=status.HTTP_400_BAD_REQUEST)
        
    from apps.attendance.utils import is_holiday, is_week_off
    # Assume get_current_company exists or is imported
    company = get_current_company(request)
    
    is_hol, hol_obj = is_holiday(parsed_date, company=company)
    
    # We check week off for the current user's employee profile if they are an employee
    is_wo = False
    if hasattr(request.user, "employee_profile"):
        is_wo = is_week_off(parsed_date, request.user.employee_profile)
        
    return Response({
        "is_holiday": bool(is_hol),
        "holiday_name": hol_obj.holiday_name if hol_obj else None,
        "holiday_type": hol_obj.holiday_type if hol_obj else None,
        "is_week_off": is_wo
    })