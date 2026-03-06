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
from .models import Attendance, Holiday
from .serializers import AttendanceSerializer
from apps.accounts.permissions import IsEmployee, IsHR
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
from apps.attendance.models import Holiday
# from apps.attendance.models import Holiday, WeekendPolicy
from apps.attendance.models import Holiday, WorkCalendar
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
from apps.attendance.models import Holiday
from datetime import date
from django.utils import timezone
from django.db import transaction
from apps.attendance.models import Attendance, Holiday
from apps.employees.models import Employee
from apps.leaves.models import LeaveRequest
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from apps.accounts.permissions import IsHR
from apps.attendance.utils import is_payroll_closed
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
        date__year=year,
        date__month=month
    ).values_list("date", flat=True)

    holiday_dates = set(holidays)

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

    attendance, created = Attendance.objects.get_or_create(
        employee=employee,
        date=today,
        defaults={"status": "PRESENT"}
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
        "holiday_days": holiday_days,
        "present_days": present_days,
        "half_days": half_days,
        "paid_leave_days": paid_leave_days,
        "unpaid_leave_days": unpaid_leave_days,
        "absent_days": absent_days,
        "late_days": late_days,
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
    employee_id = request.data.get("employee_id")
    date_value = request.data.get("date")  # YYYY-MM-DD
    status_value = request.data.get("status")  # PRESENT / ABSENT / LEAVE etc.
    check_in_value = request.data.get("check_in")  # Optional (ISO format)

    # ============================
    # VALIDATION
    # ============================

    if not employee_id or not date_value or not status_value:
        return Response(
            {"error": "employee_id, date and status are required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    valid_statuses = dict(Attendance.STATUS_CHOICES).keys()

    if status_value.upper() not in valid_statuses:
        return Response(
            {"error": "Invalid status value"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        employee = Employee.objects.get(id=employee_id)
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
    # CREATE OR UPDATE ATTENDANCE
    # ============================

    attendance, created = Attendance.objects.get_or_create(
        employee=employee,
        date=parsed_date
    )

    attendance.status = status_value.upper()

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
    date_value = request.data.get("date")
    status_value = request.data.get("status")

    if not date_value or not status_value:
        return Response(
            {"error": "date and status required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    valid_statuses = dict(Attendance.STATUS_CHOICES).keys()

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

    employees = Employee.objects.filter(is_active=True)

    attendances = [
        Attendance(employee=emp, date=parsed_date, status=status_value.upper())
        for emp in employees
    ]

    Attendance.objects.bulk_create(
        attendances,
        ignore_conflicts=True
    )

    return Response(
        {"message": "Bulk attendance marked successfully"},
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
    year = request.data.get("year")
    month = request.data.get("month")

    if not year or not month:
        return Response({"error": "Year and month required"}, status=400)

    send_monthly_attendance_manual.delay(year, month)

    return Response({"message": "Attendance emails triggered successfully"})



@api_view(["POST"])
@permission_classes([IsHR])
def generate_today_attendance(request):

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
            if Holiday.objects.filter(date=today).exists():
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