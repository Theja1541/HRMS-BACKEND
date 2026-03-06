# from django.contrib.auth.hashers import make_password
# from django.conf import settings
# from django.db import transaction
# from django.core.mail import EmailMultiAlternatives
# from rest_framework.viewsets import ModelViewSet
# from rest_framework.decorators import action
# from rest_framework.permissions import IsAuthenticated
# from rest_framework.response import Response
# from rest_framework.exceptions import ValidationError
# from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
# from django_filters.rest_framework import DjangoFilterBackend
# from rest_framework.filters import SearchFilter, OrderingFilter
# import random
# import string
# from .models import Employee, EmployeeHistory
# from .serializers import (
#     EmployeeListSerializer,
#     EmployeeDetailSerializer,
# )
# from .permissions import IsHRorAdmin
# from apps.accounts.models import User
# from rest_framework.decorators import api_view
# from rest_framework.response import Response
# from .models import Employee
# from django.contrib.auth import get_user_model

# User = get_user_model()


# class EmployeeViewSet(ModelViewSet):

#     permission_classes = [IsAuthenticated]
#     parser_classes = [MultiPartParser, FormParser, JSONParser]

#     filter_backends = [
#         DjangoFilterBackend,
#         SearchFilter,
#         OrderingFilter,
#     ]

#     search_fields = [
#         "first_name",
#         "last_name",
#         "email",
#         "employee_id",
#     ]

#     filterset_fields = ["department"]
#     ordering_fields = ["employee_id", "first_name", "created_at"]
#     ordering = ["-created_at"]

#     def get_queryset(self):
#         user = self.request.user

#         if user.role == "EMPLOYEE":
#             return Employee.objects.filter(user=user, is_active=True)

#         return Employee.objects.filter(is_active=True).select_related("user")

#     # ✅ ADD THIS METHOD
#     def perform_create(self, serializer):
#         employee = serializer.save()

#         # Only create login if not already linked
#         if not employee.user:
#             user = User.objects.create_user(
#                 username=employee.email,
#                 email=employee.email,
#                 password="Temp@123",  # temporary password
#             )

#             employee.user = user
#             employee.save()

#     def get_serializer_class(self):
#         if self.action == "list":
#             return EmployeeListSerializer
#         return EmployeeDetailSerializer

#     def get_permissions(self):
#         if self.action in ["create", "update", "partial_update", "destroy"]:
#             return [IsHRorAdmin()]
#         return [IsAuthenticated()]

#     def perform_create(self, serializer):
#         email = serializer.validated_data.get("email")

#         if User.objects.filter(username=email).exists():
#             raise ValidationError("User with this email already exists.")

#         temp_password = ''.join(
#             random.choices(string.ascii_letters + string.digits, k=10)
#         )

#         with transaction.atomic():

#             user = User.objects.create(
#                 username=email,
#                 email=email,
#                 role="EMPLOYEE",
#                 password=make_password(temp_password),
#                 must_change_password=True,
#             )

#             employee = serializer.save(user=user, is_active=True)

#             try:
#                 self.send_onboarding_email(
#                     employee=employee,
#                     email=email,
#                     temp_password=temp_password
#                 )
#             except Exception:
#                 pass
            
#     def perform_update(self, serializer):
#         instance = self.get_object()
#         old_data = {
#             field: getattr(instance, field)
#             for field in serializer.validated_data.keys()
#         }

#         employee = serializer.save()

#         for field, old_value in old_data.items():
#             new_value = getattr(employee, field)
#             if str(old_value) != str(new_value):
#                 EmployeeHistory.objects.create(
#                     employee=employee,
#                     changed_by=self.request.user,
#                     field_name=field,
#                     old_value=old_value,
#                     new_value=new_value
#                 )

#     def perform_destroy(self, instance):
#         instance.is_active = False
#         instance.save()

#     @action(detail=False, methods=["get"])
#     def me(self, request):
#         employee = request.user.employee_profile
#         serializer = self.get_serializer(employee)
#         return Response(serializer.data)

#     def send_onboarding_email(self, employee, email, temp_password):

#         login_url = "http://localhost:5173/login"

#         subject = "Welcome to HRMS – Your Account Details"

#         text_content = f"""
# Hello {employee.first_name},

# Your HRMS account has been created.

# Username: {email}
# Temporary Password: {temp_password}

# Please login and change your password immediately.

# Login here: {login_url}

# Regards,
# HR Team
# """

#         html_content = f"""
#         <div style="font-family: Arial; padding: 20px;">
#             <h2>Welcome to HRMS 🎉</h2>
#             <p>Hello <strong>{employee.first_name}</strong>,</p>
#             <p>Your HRMS account has been created.</p>
#             <h3>Login Credentials</h3>
#             <p><strong>Username:</strong> {email}</p>
#             <p><strong>Temporary Password:</strong> {temp_password}</p>
#             <p>
#                 <a href="{login_url}"
#                 style="background:#2563eb; color:white; padding:10px 18px;
#                 text-decoration:none; border-radius:5px;">
#                 Login to HRMS
#                 </a>
#             </p>
#             <p style="color:red;">
#                 ⚠ Please change your password after login.
#             </p>
#             <p>Regards,<br><strong>HR Team</strong></p>
#         </div>
#         """

#         email_message = EmailMultiAlternatives(
#             subject,
#             text_content,
#             settings.DEFAULT_FROM_EMAIL,
#             [email],
#         )

#         email_message.attach_alternative(html_content, "text/html")
#         email_message.send(fail_silently=False)

# @action(detail=False, methods=["get"], url_path="check-id")
# def check_employee_id(self, request):
#     employee_id = request.query_params.get("employee_id")
#     employee_pk = request.query_params.get("employee_pk")

#     queryset = Employee.objects.filter(employee_id=employee_id)

#     if employee_pk:
#         queryset = queryset.exclude(pk=employee_pk)

#     return Response({"exists": queryset.exists()})


# hrms_backend/apps/employees/views.py

from django.contrib.auth.hashers import make_password
from django.conf import settings
from django.db import transaction
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone
from django.db.models import Count
from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
import random
import string
from datetime import timedelta
from .models import Employee, EmployeeHistory
from .serializers import EmployeeListSerializer, EmployeeDetailSerializer
from .permissions import IsHRorAdmin
from apps.accounts.models import User
from apps.attendance.models import Attendance
from apps.leaves.models import LeaveBalance, LeaveRequest
from apps.payroll.models import Payslip
from apps.notifications.models import Notification
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Count, Q
from apps.accounts.permissions import IsEmployee
from apps.leaves.models import LeaveRequest
from apps.attendance.models import Attendance
from apps.payroll.models import Payslip
from apps.notifications.models import Notification
from datetime import date
import calendar
import json
from apps.payroll.models import Salary


class EmployeeViewSet(ModelViewSet):

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    filter_backends = [
        DjangoFilterBackend,
        SearchFilter,
        OrderingFilter,
    ]

    search_fields = ["first_name", "last_name", "email", "employee_id"]
    filterset_fields = ["department"]
    ordering_fields = ["employee_id", "first_name", "created_at"]
    ordering = ["-created_at"]

    # =====================================================
    # QUERYSET
    # =====================================================

    def get_queryset(self):
        user = self.request.user

        if user.role == "EMPLOYEE":
            return Employee.objects.filter(user=user, is_active=True).select_related("salary")

        return Employee.objects.filter(is_active=True).select_related("user", "salary")
    # =====================================================
    # SERIALIZER
    # =====================================================

    def get_serializer_class(self):
        if self.action == "list":
            return EmployeeListSerializer
        return EmployeeDetailSerializer

    # =====================================================
    # PERMISSIONS
    # =====================================================

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsHRorAdmin()]
        return [IsAuthenticated()]

    # =====================================================
    # CREATE EMPLOYEE
    # =====================================================


    def perform_create(self, serializer):

        email = serializer.validated_data.get("email")

        if User.objects.filter(username=email).exists():
            raise ValidationError("User with this email already exists.")

        temp_password = ''.join(
            random.choices(string.ascii_letters + string.digits, k=10)
        )

        with transaction.atomic():

            user = User.objects.create(
                username=email,
                email=email,
                role="EMPLOYEE",
                password=make_password(temp_password),
                must_change_password=True,
            )

            employee = serializer.save(user=user, is_active=True)

            try:
                self.send_onboarding_email(
                    employee=employee,
                    email=email,
                    temp_password=temp_password
                )
            except Exception:
                pass

    # =====================================================
    # UPDATE EMPLOYEE (WITH HISTORY)
    # =====================================================

    def perform_update(self, serializer):

        request = self.request
        salary_data = request.data.get("salary")

        if salary_data:
            salary_data = json.loads(salary_data)

        employee = serializer.save()

        # 🔥 UPDATE SALARY
        if salary_data:
            salary_obj, created = Salary.objects.get_or_create(employee=employee)

            for key, value in salary_data.items():
                setattr(salary_obj, key, value)

            salary_obj.save()

    # =====================================================
    # SOFT DELETE
    # =====================================================

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save()

    # =====================================================
    # CURRENT EMPLOYEE PROFILE
    # =====================================================

    @action(detail=False, methods=["get"])
    def me(self, request):
        employee = request.user.employee_profile
        serializer = self.get_serializer(employee)
        return Response(serializer.data)

    # =====================================================
    # CHECK EMPLOYEE ID
    # =====================================================

    @action(detail=False, methods=["get"], url_path="check-id")
    def check_employee_id(self, request):
        employee_id = request.query_params.get("employee_id")
        employee_pk = request.query_params.get("employee_pk")

        queryset = Employee.objects.filter(employee_id=employee_id)

        if employee_pk:
            queryset = queryset.exclude(pk=employee_pk)

        return Response({"exists": queryset.exists()})

    # =====================================================
    # 🔥 ENTERPRISE DASHBOARD SUMMARY (PHASE 2)
    # =====================================================

    @action(detail=False, methods=["get"], url_path="dashboard-summary")
    def dashboard_summary(self, request):

        user = request.user

        if user.role != "EMPLOYEE":
            return Response({"error": "Only employees allowed"}, status=403)

        employee = user.employee_profile
        today = timezone.now().date()
        current_year = today.year
        current_month = today.month

        # ---------------- PROFILE ----------------

        profile = {
            "employee_id": employee.employee_id,
            "name": f"{employee.first_name} {employee.last_name}",
            "designation": employee.designation,
            "department": employee.department,
            "joining_date": employee.joining_date,
            "reporting_manager": employee.reporting_manager,
            "profile_photo": employee.profile_photo.url if employee.profile_photo else None
        }

        # ---------------- ATTENDANCE (MONTH) ----------------

        monthly_records = Attendance.objects.filter(
            employee=employee,
            date__year=current_year,
            date__month=current_month
        )

        attendance = {
            "present": monthly_records.filter(status="PRESENT").count(),
            "absent": monthly_records.filter(status="ABSENT").count(),
            "leave": monthly_records.filter(status="LEAVE").count(),
        }

        today_record = monthly_records.filter(date=today).first()

        attendance.update({
            "today_status": today_record.status if today_record else "Not Marked",
            "check_in": today_record.check_in if today_record else None,
            "check_out": today_record.check_out if today_record else None
        })

        total_days = monthly_records.count()

        attendance["attendance_percentage"] = round(
            (attendance["present"] / total_days) * 100 if total_days > 0 else 0,
            2
        )

        # ---------------- ATTENDANCE TREND (6 MONTHS) ----------------

        attendance_trend = []

        for i in range(6):
            month_date = today.replace(day=1) - timedelta(days=30 * i)

            records = Attendance.objects.filter(
                employee=employee,
                date__year=month_date.year,
                date__month=month_date.month
            )

            attendance_trend.append({
                "month": month_date.strftime("%b %Y"),
                "present": records.filter(status="PRESENT").count()
            })

        attendance_trend.reverse()

        # ---------------- LEAVE SUMMARY ----------------

        leave_balances = LeaveBalance.objects.filter(
            employee=employee,
            year=current_year
        )

        leave_summary = {
            "total_balance": sum(lb.remaining for lb in leave_balances),
            "pending_requests": LeaveRequest.objects.filter(
                employee=employee,
                status="PENDING"
            ).count()
        }

        # ---------------- PAYROLL ----------------

        last_payslip = Payslip.objects.filter(
            employee=employee
        ).order_by("-month").first()

        payroll = None

        if last_payslip:
            payroll = {
                "month": last_payslip.month,
                "basic": last_payslip.basic_salary,
                "allowances": last_payslip.allowances,
                "deductions": last_payslip.deductions,
                "net_salary": last_payslip.net_pay,
                "status": last_payslip.status
            }

        salary_trend_qs = Payslip.objects.filter(
            employee=employee
        ).order_by("-month")[:6]

        salary_trend = [
            {
                "month": p.month.strftime("%b %Y"),
                "net_salary": p.net_pay
            }
            for p in reversed(salary_trend_qs)
        ]

        # ---------------- NOTIFICATIONS ----------------

        notifications = Notification.objects.filter(
            user=user
        ).order_by("-created_at")[:5]

        notification_data = [
            {
                "title": n.title,
                "message": n.message,
                "created_at": n.created_at
            }
            for n in notifications
        ]

        return Response({
            "profile": profile,
            "attendance": attendance,
            "leave": leave_summary,
            "payroll": payroll,
            "notifications": notification_data,
            "attendance_trend": attendance_trend,
            "salary_trend": salary_trend
        })

    # =====================================================
    # SEND ONBOARDING EMAIL
    # =====================================================

    def send_onboarding_email(self, employee, email, temp_password):

        login_url = "http://localhost:5173/login"

        subject = "Welcome to HRMS – Your Account Details"

        text_content = f"""
Hello {employee.first_name},

Your HRMS account has been created.

Username: {email}
Temporary Password: {temp_password}

Please login and change your password immediately.

Login here: {login_url}

Regards,
HR Team
"""

        html_content = f"""
<div style="font-family: Arial; padding: 20px;">
    <h2>Welcome to HRMS 🎉</h2>
    <p>Hello <strong>{employee.first_name}</strong>,</p>
    <p>Your HRMS account has been created.</p>
    <p><strong>Username:</strong> {email}</p>
    <p><strong>Temporary Password:</strong> {temp_password}</p>
    <p>Please change your password after login.</p>
</div>
"""

        email_message = EmailMultiAlternatives(
            subject,
            text_content,
            settings.DEFAULT_FROM_EMAIL,
            [email],
        )

        email_message.attach_alternative(html_content, "text/html")
        email_message.send(fail_silently=False)



@api_view(["GET"])
@permission_classes([IsEmployee])
def employee_dashboard(request):

    employee = request.user.employee_profile
    today = timezone.now().date()
    first_day_of_month = date(today.year, today.month, 1)

    payslip = Payslip.objects.filter(
        employee=employee,
        month__year=today.year,
        month__month=today.month
    ).first()

    # ==============================
    # 1️⃣ LEAVE SUMMARY
    # ==============================
    leaves = LeaveRequest.objects.filter(employee=employee)

    leave_summary = leaves.aggregate(
        total=Count("id"),
        pending=Count("id", filter=Q(status="PENDING")),
        approved=Count("id", filter=Q(status="APPROVED")),
        rejected=Count("id", filter=Q(status="REJECTED")),
    )

    pending_leaves = leave_summary.get("pending", 0) or 0

    # ==============================
    # 2️⃣ ATTENDANCE PERCENTAGE
    # ==============================
    year = today.year
    month = today.month

    attendance_records = Attendance.objects.filter(
        employee=employee,
        date__year=year,
        date__month=month
    )

    total_present = attendance_records.filter(
        status__in=["PRESENT", "PAID_LEAVE"]
    ).count()

    total_days = attendance_records.count()

    attendance_percentage = 0

    if total_days > 0:
        attendance_percentage = round(
            (total_present / total_days) * 100,
            2
        )

    # ==============================
    # 3️⃣ SALARY THIS MONTH
    # ==============================
    salary_this_month = 0

    today = timezone.now().date()

    payslip = Payslip.objects.filter(
        employee=employee,
        month__year=today.year,
        month__month=today.month
    ).first()

    if payslip:
        salary_this_month = payslip.net_pay

    # ==============================
    # 4️⃣ UNREAD NOTIFICATIONS
    # ==============================
    notifications_unread = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).count()

    # ==============================
    # FINAL RESPONSE
    # ==============================
    return Response({
        "leave_summary": leave_summary,
        "attendance_percentage": attendance_percentage,
        "pending_leaves": pending_leaves,
        "salary_this_month": salary_this_month,
        "notifications_unread": notifications_unread
    })

def create(self, request, *args, **kwargs):

    salary_data = request.data.get("salary")

    if salary_data:
        import json
        salary_data = json.loads(salary_data)

    serializer = self.get_serializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    employee = serializer.save()

    # 🔥 CREATE SALARY
    if salary_data:
        from apps.payroll.models import Salary

        Salary.objects.create(
            employee=employee,
            **salary_data
        )

    return Response(serializer.data)


def update(self, request, *args, **kwargs):

    salary_data = request.data.get("salary")

    if salary_data:
        import json
        salary_data = json.loads(salary_data)

    partial = kwargs.pop("partial", False)
    instance = self.get_object()

    serializer = self.get_serializer(instance, data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True)

    employee = serializer.save()

    # 🔥 UPDATE SALARY
    if salary_data:
        from apps.payroll.models import Salary

        salary_obj, created = Salary.objects.get_or_create(employee=employee)

        for key, value in salary_data.items():
            setattr(salary_obj, key, value)

        salary_obj.save()

    return Response(serializer.data)