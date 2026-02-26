from datetime import date, datetime
from collections import defaultdict

from django.utils import timezone

from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAdminUser

from .models import Attendance
from .serializers import AttendanceSerializer
from apps.accounts.permissions import IsEmployee, IsHR
from apps.employees.models import Employee


# ============================================================
# EMPLOYEE CHECK-IN
# ============================================================

@api_view(['POST'])
@permission_classes([IsEmployee])
def check_in(request):
    employee = request.user.employee_profile
    today = date.today()

    attendance, created = Attendance.objects.get_or_create(
        employee=employee,
        date=today
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
        {"message": "Check-in successful"},
        status=status.HTTP_200_OK
    )


# ============================================================
# EMPLOYEE CHECK-OUT
# ============================================================

@api_view(['POST'])
@permission_classes([IsEmployee])
def check_out(request):
    employee = request.user.employee_profile
    today = date.today()

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
    attendance.save()

    return Response(
        {"message": "Check-out successful"},
        status=status.HTTP_200_OK
    )


# ============================================================
# EMPLOYEE: VIEW OWN MONTHLY ATTENDANCE
# ============================================================

# @api_view(["GET"])
# @permission_classes([IsEmployee])
# def my_attendance(request):
#     employee = request.user.employee_profile
#     month = request.query_params.get("month")

#     if not month:
#         return Response({"error": "Month required"}, status=400)

#     year, month_num = map(int, month.split("-"))

#     records = Attendance.objects.filter(
#         employee=employee,
#         date__year=year,
#         date__month=month_num
#     )

#     data = [
#         {
#             "date": r.date.strftime("%Y-%m-%d"),
#             "status": r.status
#         }
#         for r in records
#     ]

#     return Response(data)


from django.db.models import Count

@api_view(["GET"])
@permission_classes([IsEmployee])
def my_attendance(request):
    employee = request.user.employee_profile
    month = request.query_params.get("month")

    if not month:
        return Response({"error": "Month required (YYYY-MM)"}, status=400)

    try:
        date_obj = datetime.strptime(month, "%Y-%m")
        year = date_obj.year
        month_num = date_obj.month
    except ValueError:
        return Response({"error": "Invalid month format. Use YYYY-MM"}, status=400)

    records = Attendance.objects.filter(
        employee=employee,
        date__year=year,
        date__month=month_num
    ).order_by("date")

    summary = records.values("status").annotate(count=Count("id"))

    summary_dict = {item["status"]: item["count"] for item in summary}

    data = [
        {
            "date": r.date.strftime("%Y-%m-%d"),
            "status": r.status
        }
        for r in records
    ]

    return Response({
        "summary": summary_dict,
        "records": data
    })

# ============================================================
# HR: GROUPED ATTENDANCE LIST (IMPORTANT FOR FRONTEND)
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
            "marked_at": record.marked_at,
            "check_in": record.check_in,
            "check_out": record.check_out,
        }

    return Response(grouped)


# ============================================================
# HR: MONTHLY REPORT (FLAT LIST)
# ============================================================

@api_view(['GET'])
@permission_classes([IsHR])
def monthly_report(request):
    month = request.query_params.get('month')  # YYYY-MM

    if not month:
        return Response(
            {"error": "month query param required (YYYY-MM)"},
            status=status.HTTP_400_BAD_REQUEST
        )

    year, month_num = map(int, month.split('-'))

    records = Attendance.objects.filter(
        date__year=year,
        date__month=month_num
    )

    serializer = AttendanceSerializer(records, many=True)
    return Response(serializer.data)


# ============================================================
# HR: MARK SINGLE ATTENDANCE
# ============================================================

@api_view(['POST'])
@permission_classes([IsHR])
def mark_attendance(request):
    employee_id = request.data.get("employee_id")
    date_value = request.data.get("date")
    status_value = request.data.get("status")

    if not employee_id or not date_value or not status_value:
        return Response(
            {"error": "employee_id, date and status are required"},
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
    except ValueError:
        return Response(
            {"error": "Invalid date format. Use YYYY-MM-DD"},
            status=status.HTTP_400_BAD_REQUEST
        )

    attendance, _ = Attendance.objects.get_or_create(
        employee=employee,
        date=parsed_date
    )

    attendance.status = status_value.upper()
    attendance.save()

    return Response(
        {"message": "Attendance marked successfully"},
        status=status.HTTP_200_OK
    )


# ============================================================
# HR: BULK MARK ATTENDANCE
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

    try:
        parsed_date = datetime.strptime(date_value, "%Y-%m-%d").date()
    except ValueError:
        return Response(
            {"error": "Invalid date format. Use YYYY-MM-DD"},
            status=status.HTTP_400_BAD_REQUEST
        )

    employees = Employee.objects.filter(is_active=True)

    for emp in employees:
        attendance, _ = Attendance.objects.get_or_create(
            employee=emp,
            date=parsed_date
        )

        attendance.status = status_value.upper()
        attendance.save()

    return Response(
        {"message": "Bulk attendance marked successfully"},
        status=status.HTTP_200_OK
    )


# ============================================================
# SUPER ADMIN: UNLOCK (OPTIONAL – SAFE TO KEEP)
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