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

from datetime import date, timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.accounts.models import TemporaryPasswordRecord, User
from apps.accounts.permissions import IsEmployee
from apps.accounts.tenant_utils import TenantMixin, get_current_company
from apps.audit.utils import log_action
from apps.accounts.services.temporary_passwords import (
    TemporaryPasswordEmailError,
    issue_and_send_temporary_password,
    send_temporary_password_email,
)
from apps.attendance.models import Attendance
from apps.leaves.models import LeaveBalance, LeaveRequest
from apps.notifications.models import Notification
from apps.payroll.models import Payslip, Salary
from apps.payroll.serializers import EmployeeSalarySerializer
from .models import Employee
from .permissions import IsHRorAdmin
from .serializers import (
    EmployeeDetailSerializer,
    EmployeeListSerializer,
    parse_salary_payload,
    save_employee_salary,
)


class EmployeeViewSet(TenantMixin, ModelViewSet):

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
        company = get_current_company(self.request)
        is_active = self.request.query_params.get("is_active", "true")
        role_filter = self.request.query_params.get("role")

        if user.role == "EMPLOYEE":
            base = Employee.objects.filter(user=user, is_active=True)
        else:
            # Tenant isolation: restrict to current company (SuperAdmin with no company sees all)
            base = Employee.objects.all()
            if company is not None:
                base = base.filter(user__company=company)
            # SuperAdmin can filter by company_id query param (e.g. for company detail page)
            if user.role == "SUPER_ADMIN":
                company_id = self.request.query_params.get("company_id")
                if company_id:
                    base = base.filter(user__company_id=company_id)

            if self.action == "activate":
                base = base.filter(is_active=False)
            elif str(is_active).lower() == "false":
                base = base.filter(is_active=False)
            else:
                base = base.filter(is_active=True)

            if role_filter:
                base = base.filter(designation__icontains=role_filter)

        return base.select_related("user", "salary")
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
        if self.action in [
            "create",
            "update",
            "partial_update",
            "destroy",
            "activate",
            "resend_onboarding_credentials",
            "salary",
            "roles",
            "delete_role",
            "departments",
            "delete_department",
        ]:
            return [IsHRorAdmin()]
        return [IsAuthenticated()]

    # =====================================================
    # CREATE EMPLOYEE
    # =====================================================


    def perform_create(self, serializer):
        company = get_current_company(self.request)
        # Allow Super Admin to create employees for a specific company by passing `company_id`.
        if company is None and self.request.user.role != "SUPER_ADMIN":
            raise ValidationError("Cannot create employee: no company context.")
        if company is None and self.request.user.role == "SUPER_ADMIN":
            # Try to read company_id from request data (POST body or query params)
            company_id = self.request.data.get("company_id") or self.request.query_params.get("company_id")
            if company_id:
                try:
                    from apps.accounts.models import Company

                    company = Company.objects.filter(id=company_id).first()
                except Exception:
                    company = None

        email = serializer.validated_data.get("email")
        requested_role = str(self.request.data.get("role", "EMPLOYEE")).upper().strip()
        valid_roles = {choice[0] for choice in User.ROLE_CHOICES}
        role = requested_role if requested_role in valid_roles else "EMPLOYEE"

        # Login is email-based, so user email must remain globally unique.
        if User.objects.filter(email=email).exists():
            raise ValidationError("User with this email already exists.")

        with transaction.atomic():
            user = User.objects.create(
                username=email,
                email=email,
                role=role,
                company=company,
                must_change_password=True,
            )
            user.set_unusable_password()
            user.save(update_fields=["password"])

            employee = serializer.save(user=user, is_active=True)

            log_action(
                self.request, "CREATE", "Employee",
                object_id=employee.id,
                description=f"Admin created employee: {employee.first_name} {employee.last_name} ({employee.email})",
                company=company,
            )
            try:
                issue_and_send_temporary_password(
                    user=user,
                    purpose=TemporaryPasswordRecord.PURPOSE_ONBOARDING,
                    issued_by=self.request.user if self.request.user.is_authenticated else None,
                    recipient_name=employee.first_name,
                )
            except TemporaryPasswordEmailError as exc:
                import logging
                logger = logging.getLogger(__name__)
                logger.exception("Failed to send temporary password email to user %s (%s)", user.id, user.email)
                # Do not fail employee creation if email sending fails; continue and log the issue.

    # =====================================================
    # UPDATE EMPLOYEE (WITH HISTORY)
    # =====================================================

    def perform_update(self, serializer):
        instance = self.get_object()
        tracked_fields = list(serializer.validated_data.keys())
        old_values = {field: getattr(instance, field, None) for field in tracked_fields}
        requested_role = str(self.request.data.get("role", "")).upper().strip()

        employee = serializer.save()

        if requested_role and employee.user:
            valid_roles = {choice[0] for choice in User.ROLE_CHOICES}
            normalized_role = requested_role if requested_role in valid_roles else "EMPLOYEE"
            if employee.user.role != normalized_role:
                employee.user.role = normalized_role
                employee.user.save(update_fields=["role"])

        for field in tracked_fields:
            old_value = old_values.get(field)
            new_value = getattr(employee, field, None)
            if str(old_value) != str(new_value):
                # Append change to employee.history JSONField
                employee.history.append({
                    "field_name": field,
                    "old_value": old_value,
                    "new_value": new_value,
                    "changed_by": self.request.user.id if self.request.user.is_authenticated else None,
                    "changed_at": timezone.now().isoformat(),
                })
                employee.save(update_fields=["history"])

    # =====================================================
    # SOFT DELETE
    # =====================================================

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save()

    # =====================================================
    # CURRENT EMPLOYEE PROFILE
    # =====================================================

    @action(detail=False, methods=["get", "patch", "put"])
    def me(self, request):
        employee = request.user.employee_profile
        
        if request.method == "GET":
            serializer = self.get_serializer(employee)
            return Response(serializer.data)
        
        serializer = self.get_serializer(employee, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
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

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        employee = self.get_object()
        employee.is_active = True
        employee.save()
        return Response({"message": "Employee activated successfully"})

    @action(detail=True, methods=["post"], url_path="resend-onboarding-credentials")
    def resend_onboarding_credentials(self, request, pk=None):
        employee = self.get_object()
        user = employee.user

        if not user:
            raise ValidationError({"message": "This employee does not have a linked login account."})

        try:
            with transaction.atomic():
                issue_and_send_temporary_password(
                    user=user,
                    purpose=TemporaryPasswordRecord.PURPOSE_ONBOARDING,
                    issued_by=request.user if request.user.is_authenticated else None,
                    recipient_name=employee.first_name,
                )
        except TemporaryPasswordEmailError as exc:
            raise ValidationError({"message": str(exc)}) from exc

        return Response({"message": "Onboarding credentials sent successfully."})

    @action(detail=True, methods=["get", "put"], url_path="salary")
    def salary(self, request, pk=None):
        employee = self.get_object()

        if request.method == "GET":
            salary = Salary.objects.filter(employee=employee).first()
            if not salary:
                return Response(
                    {"detail": "Salary structure not found."},
                    status=404,
                )
            return Response(EmployeeSalarySerializer(salary).data)

        raw_salary = request.data.get("salary", request.data)
        salary_data = parse_salary_payload(raw_salary)

        if salary_data is None:
            raise ValidationError({"salary": "Salary payload is required."})

        salary = save_employee_salary(employee, salary_data)
        return Response(EmployeeSalarySerializer(salary).data)

    @action(detail=False, methods=["get", "post"])
    def roles(self, request):
        from .models import CustomRole

        company = get_current_company(request)
        if company is None and request.user.role == "SUPER_ADMIN":
            company_id = request.query_params.get("company_id") or request.data.get("company_id")
            if company_id:
                try:
                    from apps.accounts.models import Company
                    company = Company.objects.filter(id=company_id).first()
                except Exception:
                    pass

        base_employees = Employee.objects.filter(is_active=True)
        if company is not None:
            base_employees = base_employees.filter(user__company=company)

        if request.method == "GET":
            designations = base_employees.values_list("designation", flat=True).distinct()
            custom_roles = CustomRole.objects.filter(company=company).values_list("name", flat=True) if company else CustomRole.objects.values_list("name", flat=True)
            all_roles = list(set(list(designations) + list(custom_roles)))
            all_roles.sort()
            return Response({"roles": all_roles})

        elif request.method == "POST":
            role = request.data.get("role", "").strip()
            if not role:
                return Response({"error": "Role name required"}, status=400)
            CustomRole.objects.get_or_create(company=company, name=role, defaults={"company": company})
            return Response({"message": "Role added successfully"})

    @action(detail=False, methods=["delete"], url_path="roles/(?P<role_name>[^/.]+)")
    def delete_role(self, request, role_name=None):
        from .models import CustomRole

        company = get_current_company(request)
        if company is None and request.user.role == "SUPER_ADMIN":
            company_id = request.query_params.get("company_id") or request.data.get("company_id")
            if company_id:
                try:
                    from apps.accounts.models import Company
                    company = Company.objects.filter(id=company_id).first()
                except Exception:
                    pass

        qs = CustomRole.objects.filter(name=role_name)
        if company is not None:
            qs = qs.filter(company=company)
        qs.delete()
        return Response({"message": "Role deleted successfully"})

    @action(detail=False, methods=["get", "post"])
    def departments(self, request):
        from .models import CustomDepartment

        company = get_current_company(request)
        if company is None and request.user.role == "SUPER_ADMIN":
            company_id = request.query_params.get("company_id") or request.data.get("company_id")
            if company_id:
                try:
                    from apps.accounts.models import Company
                    company = Company.objects.filter(id=company_id).first()
                except Exception:
                    pass

        base_employees = Employee.objects.filter(is_active=True)
        if company is not None:
            base_employees = base_employees.filter(user__company=company)

        if request.method == "GET":
            departments = base_employees.values_list("department", flat=True).distinct()
            custom_departments = CustomDepartment.objects.filter(company=company).values_list("name", flat=True) if company else CustomDepartment.objects.values_list("name", flat=True)
            all_departments = list(set(list(departments) + list(custom_departments)))
            all_departments.sort()
            return Response({"departments": all_departments})

        elif request.method == "POST":
            department = request.data.get("department", "").strip()
            if not department:
                return Response({"error": "Department name required"}, status=400)
            CustomDepartment.objects.get_or_create(company=company, name=department, defaults={"company": company})
            return Response({"message": "Department added successfully"})

    @action(detail=False, methods=["delete"], url_path="departments/(?P<department_name>[^/.]+)")
    def delete_department(self, request, department_name=None):
        from .models import CustomDepartment

        company = get_current_company(request)
        if company is None and request.user.role == "SUPER_ADMIN":
            company_id = request.query_params.get("company_id") or request.data.get("company_id")
            if company_id:
                try:
                    from apps.accounts.models import Company
                    company = Company.objects.filter(id=company_id).first()
                except Exception:
                    pass

        qs = CustomDepartment.objects.filter(name=department_name)
        if company is not None:
            qs = qs.filter(company=company)
        qs.delete()
        return Response({"message": "Department deleted successfully"})

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
            gross_salary = (
                (last_payslip.basic or 0)
                + (last_payslip.da or 0)
                + (last_payslip.hra or 0)
                + (last_payslip.conveyance or 0)
                + (last_payslip.medical or 0)
                + (last_payslip.special_allowance or 0)
            )
            total_deductions = (
                (last_payslip.fixed_deductions or 0)
                + (last_payslip.lop_deduction or 0)
            )
            payroll = {
                "month": last_payslip.month,
                "basic": last_payslip.basic,
                "gross_salary": gross_salary,
                "deductions": total_deductions,
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
        send_temporary_password_email(
            user=employee.user,
            temp_password=temp_password,
            purpose=TemporaryPasswordRecord.PURPOSE_ONBOARDING,
            recipient_name=employee.first_name,
        )



    @action(detail=False, methods=["get"], url_path="department-distribution")
    def department_distribution(self, request):
        from django.db.models import Count
        qs = self.get_queryset()
        data = qs.values("department").annotate(count=Count("id")).order_by("-count")
        
        formatted_data = []
        for item in data:
            dept = item["department"]
            if not dept:
                dept = "Unassigned"
            formatted_data.append({
                "name": dept,
                "value": item["count"]
            })
            
        return Response(formatted_data)



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