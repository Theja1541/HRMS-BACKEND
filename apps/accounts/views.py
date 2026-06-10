import logging
import os
import uuid
from datetime import timedelta

from PIL import Image
from django.contrib.auth.password_validation import validate_password
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Count, Sum, Q
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from .models import User, Company
from .serializers import (
    LoginSerializer,
    UserSerializer,
    CreateUserSerializer,
    UpdateUserRoleSerializer,
    CompanySerializer,
)
from .permissions import (
    IsAdmin,
    IsCompanyAdminOrHR,
    IsHR,
    IsEmployee,
    IsSuperAdmin,
    normalize_role,
)
from apps.employees.models import Employee
# from apps.leaves.models import Leave
from apps.leaves.models import LeaveRequest
from apps.payroll.models import Payslip
from apps.attendance.models import Attendance
from .models import TemporaryPasswordRecord
from apps.audit.utils import log_action
from .services.temporary_passwords import (
    TemporaryPasswordEmailError,
    consume_temporary_password,
    invalidate_temporary_password,
    issue_and_send_temporary_password,
)
from apps.superadmin.services import (
    issue_token_pair_for_user,
    is_password_expired,
    validate_password_against_settings,
    get_int_setting,
    get_bool_setting,
)


logger = logging.getLogger(__name__)

COMPANY_SCOPED_ROLES = {"ADMIN", "HR", "EMPLOYEE"}
AUTO_PASSWORD_EMAIL_ROLES = {"ADMIN", "HR"}

MAX_COMPANY_LOGO_BYTES = 2 * 1024 * 1024
ALLOWED_LOGO_CONTENT_TYPES = frozenset({"image/png", "image/jpeg", "image/webp", "image/svg+xml"})
ALLOWED_LOGO_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp", ".svg"})


@api_view(["POST"])
@permission_classes([AllowAny])
def custom_token_refresh(request):
    refresh_token = request.data.get("refresh")
    if not refresh_token:
        return Response(
            {"detail": "Refresh token is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        refresh = RefreshToken(refresh_token)
        # Issue a new refresh token to implement rolling sessions
        refresh.set_jti()
        refresh.set_exp()
        access = refresh.access_token
        
        timeout_minutes = get_int_setting("session_timeout_minutes", 60, minimum=1, maximum=525600)
        access.set_exp(lifetime=timedelta(minutes=timeout_minutes))
        refresh.set_exp(lifetime=timedelta(minutes=timeout_minutes))
    except TokenError:
        return Response(
            {"detail": "Token is invalid or expired"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    return Response({
        "access": str(access),
        "refresh": str(refresh),
    })


def _company_logo_validation_error(uploaded):
    if uploaded.size > MAX_COMPANY_LOGO_BYTES:
        return "File too large. Maximum size is 2MB."
    ext = os.path.splitext(uploaded.name or "")[1].lower()
    if ext not in ALLOWED_LOGO_EXTENSIONS:
        return "Unsupported format. Use PNG, JPG, JPEG, or WebP."
    ct = (uploaded.content_type or "").lower()
    if ct == "image/jpg":
        ct = "image/jpeg"
    if ct not in ALLOWED_LOGO_CONTENT_TYPES:
        return "Unsupported image type. Use PNG, JPG, JPEG, or WebP."
    if ext == ".svg" or ct == "image/svg+xml":
        uploaded.seek(0)
        return None
    try:
        uploaded.seek(0)
        with Image.open(uploaded) as img:
            img.verify()
    except Exception:
        return "Invalid or corrupted image file."
    uploaded.seek(0)
    return None


def _can_read_company_branding(request, company):
    """Any authenticated member of the company may read branding (e.g. sidebar logo)."""
    if not request.user or not request.user.is_authenticated:
        return False
    if not company:
        return False
    role = _normalize_role(getattr(request.user, "role", ""))
    if role == "SUPER_ADMIN":
        return True
    return getattr(request.user, "company_id", None) == getattr(company, "id", None)


def _can_manage_company_branding(request, company):
    if not request.user or not request.user.is_authenticated:
        return False
    role = _normalize_role(getattr(request.user, "role", ""))
    if role == "SUPER_ADMIN":
        return True
    if role not in {"ADMIN", "HR"}:
        return False
    return getattr(request.user, "company_id", None) == getattr(company, "id", None)


def _normalize_role(value):
    return normalize_role(value)


def _ensure_super_admin_for_logo(request):
    if not request.user or not request.user.is_authenticated:
        return Response(
            {"detail": "Authentication credentials were not provided or are invalid."},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    if _normalize_role(getattr(request.user, "role", "")) != "SUPER_ADMIN":
        return Response(
            {"detail": "Only Super Admin users can upload or remove company logos."},
            status=status.HTTP_403_FORBIDDEN,
        )
    return None


def _get_request_company(request):
    return getattr(request, "company", None) or getattr(request.user, "company", None)


def _build_auth_user_payload(user, request=None):
    employee_profile_id = None
    if user.role == "EMPLOYEE":
        try:
            employee_profile_id = user.employee_profile.id
        except Employee.DoesNotExist:
            employee_profile_id = None

    company_data = None
    if getattr(user, "company_id", None):
        company = user.company
        company_data = {
            "id": user.company_id,
            "name": company.name if company else None,
            "company_code": company.company_code if company else None,
            "domain": company.domain if company else None,
            "billing_action_stopped": company.billing_action_stopped if company else False,
            "subscription_period_end": company.subscription_period_end.isoformat() if company and company.subscription_period_end else None,
        }
        if company is not None and request is not None:
            logo_url = CompanySerializer(company, context={"request": request}).data.get(
                "logo_url"
            )
            if logo_url:
                company_data["logo_url"] = logo_url
                company_data["logoUrl"] = logo_url

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "company_id": user.company_id,
        "employee_profile_id": employee_profile_id,
        "company": company_data,
        "hr_permissions": user.hr_permissions,
    }


def _set_new_password(user, new_password):
    password_error = validate_password_against_settings(new_password)
    if password_error:
        raise DjangoValidationError(password_error)

    validate_password(new_password, user=user)

    user.set_password(new_password)
    # `password_changed_at` was removed from the User model; skip setting it.
    user.must_change_password = False
    user.failed_attempts = 0
    user.is_locked = False
    user.locked_at = None
    user.save(
        update_fields=[
            "password",
            "must_change_password",
            "failed_attempts",
            "is_locked",
            "locked_at",
        ]
    )
    invalidate_temporary_password(user)

# =========================================================
# 🔐 LOGIN (JWT)
# =========================================================

@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):

    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    user = serializer.validated_data["user"]
    temporary_password_record = serializer.validated_data.get("temporary_password_record")

    # ─── Check MFA requirement ───
    mfa_required = False
    if user.role != "SUPER_ADMIN":
        mfa_required = get_bool_setting("require_mfa", False)

    if mfa_required:
        # Don't issue tokens yet — tell frontend to show OTP screen
        log_action(
            request, "LOGIN_MFA_PENDING", "User",
            object_id=user.id,
            description=f"MFA OTP required for login: {user.email}",
            company=getattr(user, "company", None),
            user_override=user,
        )
        return Response({
            "mfa_required": True,
            "user_id": user.id,
            "email": user.email,
        }, status=status.HTTP_200_OK)

    # ─── Normal (no-MFA) login flow ──────────────────────────────
    log_action(
        request, "LOGIN", "User",
        object_id=user.id,
        description=f"User login: {user.email}",
        company=getattr(user, "company", None),
        user_override=user,
    )
    access_token, refresh_token = issue_token_pair_for_user(user)
    if temporary_password_record:
        consume_temporary_password(temporary_password_record)

    user_payload = _build_auth_user_payload(user, request)

    # 🔒 FORCE PASSWORD CHANGE
    if getattr(user, "must_change_password", False) or is_password_expired(user):
        return Response({
            "force_password_change": True,
            "access": access_token,
            "refresh": refresh_token,
            "user": user_payload,
        }, status=status.HTTP_200_OK)

    # ✅ NORMAL LOGIN
    return Response({
        "access": access_token,
        "refresh": refresh_token,
        "force_password_change": False,
        "user": user_payload,
    }, status=status.HTTP_200_OK)

# =========================================================
# 👤 CURRENT USER PROFILE
# =========================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def employee_profile(request):
    serializer = UserSerializer(request.user)
    return Response(serializer.data)


# =========================================================
# 👥 LIST USERS (ROLE BASED)
# =========================================================

@api_view(['GET'])
# @permission_classes([IsSuperAdmin])
def superadmin_user_list(request):
    # SuperAdmin can see all companies' users
    users = User.objects.select_related("company").all().order_by("-id")
    serializer = UserSerializer(users, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAdmin])
def admin_user_list(request):
    # Tenant isolation: only users of the same company
    company = getattr(request, "company", None) or getattr(request.user, "company", None)
    if not company:
        return Response({"detail": "User has no company."}, status=status.HTTP_403_FORBIDDEN)
    users = User.objects.filter(company=company).select_related("company").order_by("-id")
    serializer = UserSerializer(users, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsHR])
def hr_user_list(request):
    # Tenant isolation: only users of the same company
    company = getattr(request, "company", None) or getattr(request.user, "company", None)
    if not company:
        return Response({"detail": "User has no company."}, status=status.HTTP_403_FORBIDDEN)
    users = User.objects.filter(company=company).select_related("company").order_by("-id")
    serializer = UserSerializer(users, many=True)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsCompanyAdminOrHR])
def company_user_list(request):
    """
    Company-scoped user list for Admin/HR.
    Returns only Admin/HR users for the current company.
    """
    company = _get_request_company(request)
    if not company:
        return Response({"detail": "User has no company."}, status=status.HTTP_403_FORBIDDEN)

    users = (
        User.objects.filter(company=company, role__in=["ADMIN", "HR"])
        .select_related("company")
        .order_by("-id")
    )
    serializer = UserSerializer(users, many=True)
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([IsCompanyAdminOrHR])
@parser_classes([MultiPartParser, FormParser])
def company_user_create(request):
    """
    Admin/HR can create HR users inside their own company.
    A temporary password is generated and sent by email.
    """
    company = _get_request_company(request)
    if not company:
        return Response({"detail": "User has no company."}, status=status.HTTP_403_FORBIDDEN)

    requested_role = _normalize_role(request.data.get("role") or "HR")
    if requested_role != "HR":
        return Response(
            {"role": ["Only HR users can be created from the company portal."]},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if hasattr(request.data, "dict"):
        data = request.data.dict()
    else:
        data = request.data.copy()

    data["role"] = "HR"
    if not data.get("username"):
        data["username"] = str(data.get("email") or "").strip().lower()

    # Parse stringified json permission field from multipart/form-data
    import json
    hr_permissions = data.get("hr_permissions")
    if isinstance(hr_permissions, str):
        try:
            data["hr_permissions"] = json.loads(hr_permissions)
        except Exception:
            pass

    employee_id = data.get("employee_id")
    if employee_id:
        employee_id = str(employee_id).strip()
        if User.objects.filter(company=company, employee_id=employee_id).exists():
            return Response({"employee_id": ["Employee ID already exists."]}, status=status.HTTP_400_BAD_REQUEST)
        try:
            from apps.employees.models import Employee
            if Employee.objects.filter(company=company, employee_id=employee_id).exists():
                return Response({"employee_id": ["Employee ID already exists."]}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            pass

    serializer = CreateUserSerializer(data=data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    try:
        with transaction.atomic():
            new_user = serializer.save(company=company)
            issue_and_send_temporary_password(
                user=new_user,
                purpose=TemporaryPasswordRecord.PURPOSE_ONBOARDING,
                issued_by=request.user if request.user.is_authenticated else None,
                recipient_name=new_user.get_full_name() or new_user.email,
            )
            log_action(
                request, "CREATE", "User",
                object_id=new_user.id,
                description=f"Company user created: {new_user.email} (HR)",
                company=company,
            )
    except TemporaryPasswordEmailError as exc:
        return Response(
            {"error": str(exc)},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    except Exception:
        logger.exception("Failed to create company HR user")
        return Response(
            {"error": "Failed to create HR user. Please try again."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return Response(
        {
            "message": "HR user created successfully. Temporary password sent to email.",
            "temporary_password_email_sent": True,
            "user_id": new_user.id,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["PATCH", "PUT"])
@permission_classes([IsCompanyAdminOrHR])
@parser_classes([MultiPartParser, FormParser])
def company_user_update(request, user_id):
    """
    Admin can update HR user details and permissions inside their own company.
    """
    company = _get_request_company(request)
    if not company:
        return Response({"detail": "User has no company."}, status=status.HTTP_403_FORBIDDEN)
        
    user = get_object_or_404(User, id=user_id, company=company)
    
    # Check if target user is HR
    if user.role != "HR":
        return Response({"detail": "Only HR users can be updated from the company portal."}, status=status.HTTP_400_BAD_REQUEST)
        
    if hasattr(request.data, "dict"):
        data = request.data.dict()
    else:
        data = request.data.copy()
    
    # Parse stringified json permission field from multipart/form-data
    import json
    hr_permissions = data.get("hr_permissions")
    if isinstance(hr_permissions, str):
        try:
            data["hr_permissions"] = json.loads(hr_permissions)
        except Exception:
            pass
            
    employee_id = data.get("employee_id")
    if employee_id:
        employee_id = str(employee_id).strip()
        if User.objects.filter(company=company, employee_id=employee_id).exclude(id=user.id).exists():
            return Response({"employee_id": ["Employee ID already exists."]}, status=status.HTTP_400_BAD_REQUEST)
        try:
            from apps.employees.models import Employee
            if Employee.objects.filter(company=company, employee_id=employee_id).exclude(user=user).exists():
                return Response({"employee_id": ["Employee ID already exists."]}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            pass
            
    # Serialize and update
    serializer = UserSerializer(user, data=data, partial=True)
    if serializer.is_valid():
        updated_user = serializer.save()
        log_action(
            request, "UPDATE", "User",
            object_id=updated_user.id,
            description=f"Company user updated: {updated_user.email} (HR)",
            company=company,
        )
        return Response(serializer.data, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# =========================================================
# ➕ CREATE USER (SUPER ADMIN)
# =========================================================

@api_view(['POST'])
@permission_classes([IsSuperAdmin])
def create_user(request):
    """Super Admin can create platform users or tenant-scoped users."""
    data = request.data.copy()
    role = _normalize_role(data.get("role"))

    company_id = data.get("company_id")
    company = None
    if role not in {choice[0] for choice in User.ROLE_CHOICES}:
        return Response(
            {"role": ["Invalid role selected."]},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if company_id is not None and company_id != "":
        try:
            company = Company.objects.get(id=int(company_id), is_active=True)
        except (Company.DoesNotExist, ValueError, TypeError):
            return Response(
                {"company_id": ["Invalid company ID."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

    if role == "SUPER_ADMIN":
        if company_id not in (None, ""):
            return Response(
                {"company_id": ["Super Admin cannot belong to a company."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        company = None
    elif role in COMPANY_SCOPED_ROLES:
        if not company:
            return Response(
                {"company_id": [f"Company is required when creating a {role.title()} user."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

    serializer = CreateUserSerializer(data=data)
    if serializer.is_valid():
        try:
            with transaction.atomic():
                new_user = serializer.save(company=company)

                email_sent = False
                if role in AUTO_PASSWORD_EMAIL_ROLES:
                    issue_and_send_temporary_password(
                        user=new_user,
                        purpose=TemporaryPasswordRecord.PURPOSE_ONBOARDING,
                        issued_by=request.user if request.user.is_authenticated else None,
                        recipient_name=new_user.get_full_name() or new_user.username or new_user.email,
                    )
                    email_sent = True

                log_action(
                    request, "CREATE", "User",
                    object_id=new_user.id,
                    description=f"Platform user created: {new_user.username} ({new_user.email})",
                    company=company,
                )
        except TemporaryPasswordEmailError as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception:
            logger.exception("Failed to create user with role %s", role)
            return Response(
                {"error": "Failed to create user. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        response_payload = {
            "message": "User created successfully",
            "user_id": new_user.id,
        }
        if role in AUTO_PASSWORD_EMAIL_ROLES:
            response_payload["temporary_password_email_sent"] = email_sent
        return Response(response_payload, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# =========================================================
# 🔄 UPDATE USER ROLE
# =========================================================

@api_view(['PATCH'])
@permission_classes([IsSuperAdmin])
def update_user_role(request, user_id):
    # Only Super Admin can change roles; no tenant check needed
    user = get_object_or_404(User, id=user_id)

    # 🚫 Prevent self role change
    if user == request.user:
        return Response(
            {"error": "You cannot change your own role"},
            status=status.HTTP_400_BAD_REQUEST
        )

    serializer = UpdateUserRoleSerializer(
        user,
        data=request.data,
        partial=True
    )

    if serializer.is_valid():
        serializer.save()
        return Response({"message": "User role updated successfully"})

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# =========================================================
# ❌ DELETE USER (ADMIN / SUPER ADMIN)
# =========================================================

@api_view(['DELETE'])
@permission_classes([IsAdmin | IsSuperAdmin])
def delete_user(request, user_id):
    user = get_object_or_404(User, id=user_id)

    if user == request.user:
        return Response(
            {"error": "You cannot delete yourself"},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Tenant isolation: Company Admin can only delete users in their company
    if request.user.role == "ADMIN":
        if getattr(user, "company_id", None) != getattr(request.user, "company_id", None):
            return Response(
                {"error": "You can only delete users belonging to your company."},
                status=status.HTTP_403_FORBIDDEN,
            )

    user.delete()
    return Response({"message": "User deleted successfully"})


# =========================================================
# 🔑 SUPER ADMIN: RESET USER PASSWORD (send temp password email)
# =========================================================

@api_view(["POST"])
@permission_classes([IsSuperAdmin])
def superadmin_reset_password(request, user_id):
    user = get_object_or_404(User, id=user_id)
    try:
        with transaction.atomic():
            issue_and_send_temporary_password(
                user=user,
                purpose=TemporaryPasswordRecord.PURPOSE_PASSWORD_RESET,
                recipient_name=user.get_full_name() or user.username,
            )
    except TemporaryPasswordEmailError as exc:
        return Response(
            {"error": str(exc)},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    except Exception:
        logger.exception("SuperAdmin password reset failed for user %s", user_id)
        return Response(
            {"error": "Failed to send temporary password email. Check SMTP settings."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    log_action(
        request, "PASSWORD_RESET", "User",
        object_id=user.id,
        description=f"SuperAdmin reset password for {user.email}",
        company=getattr(user, "company", None),
    )
    return Response({"message": "Temporary password sent to user's email"})


# =========================================================
# 🚫 SUPER ADMIN: BLOCK / UNBLOCK USER
# =========================================================

@api_view(["PATCH"])
@permission_classes([IsSuperAdmin | IsCompanyAdminOrHR])
def superadmin_block_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if user == request.user:
        return Response(
            {"error": "You cannot block yourself"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Tenant check: Company-scoped admins/HR can only block/unblock users in their own company
    if getattr(request.user, "role", "").upper() != "SUPER_ADMIN":
        if getattr(user, "company_id", None) != getattr(request.user, "company_id", None):
            return Response(
                {"detail": "You can only modify users belonging to your company."},
                status=status.HTTP_403_FORBIDDEN,
            )

    is_active = request.data.get("is_active")
    if is_active is None:
        return Response(
            {"error": "is_active (true/false) is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    user.is_active = bool(is_active)
    if user.is_active:
        user.is_locked = False
        user.failed_attempts = 0
        user.locked_at = None
        user.save(update_fields=["is_active", "is_locked", "failed_attempts", "locked_at"])
    else:
        user.save(update_fields=["is_active"])
    return Response({
        "message": "User unblocked" if user.is_active else "User blocked",
        "is_active": user.is_active,
    })


# =========================================================
# 🔓 SUPER ADMIN: UNLOCK USER (clear lock from failed attempts)
# =========================================================

@api_view(["POST"])
@permission_classes([IsSuperAdmin | IsCompanyAdminOrHR])
def superadmin_unlock_user(request, user_id):
    user = get_object_or_404(User, id=user_id)

    # Tenant check: Company-scoped admins/HR can only unlock users in their own company
    if getattr(request.user, "role", "").upper() != "SUPER_ADMIN":
        if getattr(user, "company_id", None) != getattr(request.user, "company_id", None):
            return Response(
                {"detail": "You can only unlock users belonging to your company."},
                status=status.HTTP_403_FORBIDDEN,
            )

    user.is_locked = False
    user.failed_attempts = 0
    user.locked_at = None
    user.save(update_fields=["is_locked", "failed_attempts", "locked_at"])
    return Response({"message": "User unlocked", "is_locked": False})


@api_view(["POST"])
@permission_classes([IsSuperAdmin | IsCompanyAdminOrHR])
def superadmin_reset_attempts(request, user_id):
    user = get_object_or_404(User, id=user_id)

    if getattr(request.user, "role", "").upper() != "SUPER_ADMIN":
        if getattr(user, "company_id", None) != getattr(request.user, "company_id", None):
            return Response(
                {"detail": "You can only reset attempts for users belonging to your company."},
                status=status.HTTP_403_FORBIDDEN,
            )

    user.failed_attempts = 0
    user.is_locked = False
    user.locked_at = None
    user.save(update_fields=["failed_attempts", "is_locked", "locked_at"])
    return Response({"message": "User login attempts reset successfully", "failed_attempts": 0, "is_locked": False})


# =========================================================
# 🔑 CHANGE PASSWORD
# =========================================================

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_password(request):

    new_password = request.data.get("new_password")

    if not new_password:
        return Response(
            {"error": "New password required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    user = request.user

    try:
        _set_new_password(user, new_password)
    except DjangoValidationError as exc:
        return Response(
            {"error": exc.messages[0]},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response({"message": "Password changed successfully"})


# =========================================================
# 🔑 CHANGE PASSWORD WITH OLD PASSWORD VERIFICATION
# =========================================================

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_password_with_old(request):

    old_password = request.data.get("old_password")
    new_password = request.data.get("new_password")

    if not old_password or not new_password:
        return Response(
            {"error": "Both old and new passwords are required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    user = request.user

    # Verify old password
    if not user.check_password(old_password):
        return Response(
            {"error": "Old password is incorrect"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        _set_new_password(user, new_password)
    except DjangoValidationError as exc:
        return Response(
            {"error": exc.messages[0]},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response({"message": "Password changed successfully"})


# =========================================================
# 📧 FORGOT PASSWORD - SEND TEMPORARY PASSWORD
# =========================================================

@api_view(["POST"])
@permission_classes([AllowAny])
def forgot_password(request):
    email = request.data.get("email")

    if not email:
        return Response(
            {"error": "Email is required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response(
            {"error": "No user found with this email"},
            status=status.HTTP_404_NOT_FOUND
        )
    except User.MultipleObjectsReturned:
        return Response(
            {"error": "Multiple accounts exist with this email. Please contact support."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        with transaction.atomic():
            issue_and_send_temporary_password(
                user=user,
                purpose=TemporaryPasswordRecord.PURPOSE_PASSWORD_RESET,
                recipient_name=user.get_full_name() or user.username,
            )
    except TemporaryPasswordEmailError as exc:
        return Response(
            {"error": str(exc)},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    except Exception:
        logger.exception("Temporary password reset failed for %s", email)
        return Response(
            {"error": "Failed to issue a temporary password. Please try again later."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    log_action(
        request, "PASSWORD_RESET", "User",
        object_id=user.id,
        description=f"Password reset requested for {user.email}",
        company=getattr(user, "company", None),
    )
    return Response({
        "message": "Temporary password sent to your email"
    })


# =========================================================
# 📊 SUPER ADMIN ANALYTICS
# =========================================================

@api_view(["GET"])
@permission_classes([IsSuperAdmin])
def superadmin_analytics(request):
    # SuperAdmin sees system-wide stats (all tenants)
    total_users = User.objects.count()
    total_employees = Employee.objects.count()
    total_leaves = LeaveRequest.objects.count()
    total_payslips = Payslip.objects.count()
    total_attendance = Attendance.objects.count()
    # Companies: total registered, active, inactive/suspended
    total_companies_registered = Company.objects.count()
    active_companies = Company.objects.filter(is_active=True).count()
    inactive_companies = Company.objects.filter(is_active=False).count()
    total_companies = active_companies  # backward compat

    # Total payroll processed (sum of net_pay across all payslips)
    payroll_aggregate = Payslip.objects.aggregate(total=Sum("net_pay"))
    total_payroll_processed = float(payroll_aggregate["total"] or 0)

    # HR/Admin users (ADMIN + HR roles)
    hr_admin_count = User.objects.filter(role__in=["ADMIN", "HR"]).count()

    role_distribution = list(
        User.objects.values("role").annotate(count=Count("id"))
    )

    # Per-company summary for dashboard
    companies_summary = list(
        Company.objects.filter(is_active=True)
        .annotate(
            user_count=Count("users", distinct=True),
            employee_count=Count("users", filter=Q(users__role='EMPLOYEE'), distinct=True),
        )
        .values("id", "name", "company_code", "user_count", "employee_count", "is_active")
    )

    # Recent company registrations (last 10)
    recent_companies = list(
        Company.objects.all()
        .order_by("-created_at")[:10]
        .values("id", "name", "company_code", "created_at", "is_active")
    )
    for c in recent_companies:
        c["created_at"] = c["created_at"].isoformat() if c.get("created_at") else None

    # Simple system health: OK if no critical issues
    system_health = "Healthy"

    return Response({
        "total_users": total_users,
        "total_employees": total_employees,
        "total_leaves": total_leaves,
        "total_payslips": total_payslips,
        "total_attendance": total_attendance,
        "total_companies": total_companies,
        "total_companies_registered": total_companies_registered,
        "active_companies": active_companies,
        "inactive_companies": inactive_companies,
        "total_payroll_processed": total_payroll_processed,
        "hr_admin_count": hr_admin_count,
        "recent_companies": recent_companies,
        "system_health": system_health,
        "role_distribution": role_distribution,
        "companies_summary": companies_summary,
    })


# =========================================================
# 🏢 COMPANIES (TENANTS) – SuperAdmin CRUD
# =========================================================

@api_view(["GET"])
@permission_classes([IsSuperAdmin])
def company_list(request):
    is_active = request.query_params.get("is_active")
    
    from django.db.models import Prefetch
    admin_users_prefetch = Prefetch(
        "users",
        queryset=User.objects.filter(role="ADMIN"),
        to_attr="prefetched_admin_users"
    )

    qs = (
        Company.objects.annotate(employee_count=Count("users", filter=Q(users__role='EMPLOYEE')))
        .select_related("subscription", "subscription__subscription_plan")
        .prefetch_related(admin_users_prefetch)
        .order_by("name")
    )
    if is_active is not None:
        if str(is_active).lower() in ("true", "1"):
            qs = qs.filter(is_active=True)
        elif str(is_active).lower() in ("false", "0"):
            qs = qs.filter(is_active=False)
    serializer = CompanySerializer(qs, many=True, context={"request": request})
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([IsSuperAdmin])
def company_create(request):
    """
    Create a company (tenant). Optionally create the Company Admin in the same request.
    Payload: company fields (name, company_code, domain, email, ...) plus optional:
      - admin_email (required if creating admin)
      - admin_first_name, admin_last_name (optional)
    When admin_email is provided, a User with role=ADMIN and company=new_company is created
    and a temporary password is sent to admin_email.
    """
    data = request.data.copy()
    admin_email = (data.pop("admin_email", None) or "").strip().lower()
    admin_first_name = (data.pop("admin_first_name", None) or "").strip()
    admin_last_name = (data.pop("admin_last_name", None) or "").strip()

    serializer = CompanySerializer(data=data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    if admin_email and User.objects.filter(email=admin_email).exists():
        return Response(
            {"admin_email": ["A user with this email already exists."]},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        with transaction.atomic():
            company = serializer.save()

            # Activate pricing plan subscription if provided
            pricing_plan_id = request.data.get("pricing_plan") or request.data.get("pricing_plan_id")
            if pricing_plan_id:
                from datetime import datetime
                from apps.billing.models import SubscriptionPlan
                from apps.billing.services.subscription_service import SubscriptionService

                start_date_str = request.data.get("subscription_period_start")
                end_date_str = request.data.get("subscription_period_end")

                start_date = None
                if start_date_str:
                    try:
                        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                    except ValueError:
                        pass

                end_date = None
                if end_date_str:
                    try:
                        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
                    except ValueError:
                        pass

                try:
                    plan = SubscriptionPlan.objects.get(id=pricing_plan_id)
                    SubscriptionService().activate_or_renew_subscription(
                        company=company,
                        plan=plan,
                        billing_cycle="monthly",
                        start_date=start_date,
                        end_date=end_date
                    )
                except SubscriptionPlan.DoesNotExist:
                    pass

            log_action(
                request, "CREATE", "Company",
                object_id=company.id,
                description=f"Company created: {company.name}",
                company=company,
            )
            admin_user = None
            if admin_email:
                admin_user = User.objects.create(
                    username=admin_email,
                    email=admin_email,
                    first_name=admin_first_name,
                    last_name=admin_last_name,
                    role="ADMIN",
                    company=company,
                    must_change_password=True,
                )
                admin_user.set_unusable_password()
                admin_user.save(update_fields=["password"])
                issue_and_send_temporary_password(
                    user=admin_user,
                    purpose=TemporaryPasswordRecord.PURPOSE_ONBOARDING,
                    issued_by=request.user if request.user.is_authenticated else None,
                    recipient_name=admin_user.get_full_name() or admin_user.email,
                )
                log_action(
                    request, "CREATE", "User",
                    object_id=admin_user.id,
                    description=f"Company Admin created with company: {admin_user.email}",
                    company=company,
                )
            response_data = CompanySerializer(company, context={"request": request}).data
            if admin_user:
                response_data["admin_created"] = True
                response_data["admin_id"] = admin_user.id
                response_data["message"] = "Company and Company Admin created. Temporary password sent to admin email."
            else:
                response_data["message"] = "Company created successfully."
            return Response(response_data, status=status.HTTP_201_CREATED)
    except TemporaryPasswordEmailError as exc:
        return Response(
            {"error": str(exc)},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    except Exception:
        logger.exception("Company create failed")
        return Response(
            {"error": "Failed to create company. Please try again."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsSuperAdmin])
def company_detail(request, company_id):
    company = get_object_or_404(
        Company.objects.annotate(employee_count=Count("users", filter=Q(users__role='EMPLOYEE'))),
        id=company_id,
    )
    serializer = CompanySerializer(company, context={"request": request})
    return Response(serializer.data)


@api_view(["PATCH", "PUT"])
@permission_classes([IsSuperAdmin])
def company_update(request, company_id):
    company = get_object_or_404(Company, id=company_id)

    pricing_plan_id = request.data.get("pricing_plan") or request.data.get("pricing_plan_id")
    start_date_str = request.data.get("subscription_period_start")
    end_date_str = request.data.get("subscription_period_end")

    admin_email = (request.data.get("admin_email") or "").strip().lower()
    admin_first_name = (request.data.get("admin_first_name") or "").strip()
    admin_last_name = (request.data.get("admin_last_name") or "").strip()

    serializer = CompanySerializer(
        company,
        data=request.data,
        partial=True,
        context={"request": request},
    )
    if serializer.is_valid():
        try:
            with transaction.atomic():
                company = serializer.save()

                # If pricing plan was explicitly passed (even if empty or null)
                if pricing_plan_id is not None:
                    if pricing_plan_id == "" or pricing_plan_id is None:
                        # Deactivate current subscription
                        from apps.billing.models import CompanySubscription
                        CompanySubscription.objects.filter(company=company).update(is_active=False)
                    else:
                        from datetime import datetime
                        from apps.billing.models import SubscriptionPlan
                        from apps.billing.services.subscription_service import SubscriptionService

                        start_date = None
                        if start_date_str:
                            try:
                                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                            except ValueError:
                                pass

                        end_date = None
                        if end_date_str:
                            try:
                                end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
                            except ValueError:
                                pass

                        try:
                            plan = SubscriptionPlan.objects.get(id=pricing_plan_id)
                            SubscriptionService().activate_or_renew_subscription(
                                company=company,
                                plan=plan,
                                billing_cycle="monthly",
                                start_date=start_date,
                                end_date=end_date
                            )
                        except SubscriptionPlan.DoesNotExist:
                            pass
                elif start_date_str or end_date_str:
                    # If dates changed but plan stayed the same, update the dates on the active subscription
                    from datetime import datetime
                    from apps.billing.models import CompanySubscription
                    sub = CompanySubscription.objects.filter(company=company, is_active=True).first()
                    if sub:
                        if start_date_str:
                            try:
                                sub.start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                            except ValueError:
                                pass
                        if end_date_str:
                            try:
                                sub.end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
                                sub.next_billing_date = sub.end_date
                                company.subscription_period_end = sub.end_date
                                company.save(update_fields=["subscription_period_end"])
                            except ValueError:
                                pass
                        sub.save()

                # Update or create Admin user if admin_email is provided
                if admin_email:
                    admin_user = User.objects.filter(company=company, role="ADMIN").first()
                    if admin_user:
                        if admin_email:
                            admin_user.email = admin_email
                            admin_user.username = admin_email
                        if admin_first_name:
                            admin_user.first_name = admin_first_name
                        if admin_last_name:
                            admin_user.last_name = admin_last_name
                        admin_user.save(update_fields=["email", "username", "first_name", "last_name"])
                    else:
                        admin_user = User.objects.create(
                            username=admin_email,
                            email=admin_email,
                            first_name=admin_first_name,
                            last_name=admin_last_name,
                            role="ADMIN",
                            company=company,
                            must_change_password=True,
                        )
                        admin_user.set_unusable_password()
                        admin_user.save(update_fields=["password"])
                        issue_and_send_temporary_password(
                            user=admin_user,
                            purpose=TemporaryPasswordRecord.PURPOSE_ONBOARDING,
                            issued_by=request.user if request.user.is_authenticated else None,
                            recipient_name=admin_user.get_full_name() or admin_user.email,
                        )

                # Re-serialize to reflect new subscription settings
                response_serializer = CompanySerializer(company, context={"request": request})
                return Response(response_serializer.data)
        except Exception as e:
            logger.exception("Company update failed")
            return Response(
                {"error": f"Failed to update company: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST", "DELETE"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def company_logo(request, company_id):
    """
    POST: multipart field `logo` — PNG/JPEG/WebP, max 2MB.
    DELETE: remove stored logo (file + DB).
    """
    auth_error = _ensure_super_admin_for_logo(request)
    if auth_error:
        return auth_error

    company = get_object_or_404(Company, id=company_id)
    if not _can_manage_company_branding(request, company):
        return Response(
            {"detail": "You do not have permission to update this company logo."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == "DELETE":
        if hasattr(company, "clear_logo_file"):
            try:
                company.clear_logo_file()
                company.save(update_fields=["logo"])
            except Exception:
                pass
        else:
            return Response({"detail": "Company logo feature not available for this tenant."}, status=status.HTTP_400_BAD_REQUEST)
        log_action(
            request,
            "UPDATE",
            "Company",
            object_id=company.id,
            description=f"Company logo removed: {company.name}",
            company=company,
        )
        data = CompanySerializer(company, context={"request": request}).data
        data["logoUrl"] = data.get("logo_url")
        return Response(data)

    uploaded = request.FILES.get("logo")
    if not uploaded:
        return Response(
            {"logo": ["No file was submitted."]},
            status=status.HTTP_400_BAD_REQUEST,
        )

    err = _company_logo_validation_error(uploaded)
    if err:
        return Response({"error": err}, status=status.HTTP_400_BAD_REQUEST)

    if not hasattr(company, "logo"):
        return Response({"detail": "Company logo feature not available for this tenant."}, status=status.HTTP_400_BAD_REQUEST)

    if getattr(company, "logo"):
        try:
            company.logo.delete(save=False)
        except Exception:
            pass

    ext = os.path.splitext(uploaded.name or "")[1].lower()
    if ext not in ALLOWED_LOGO_EXTENSIONS:
        ext = ".png"
    storage_name = f"{uuid.uuid4().hex}{ext}"
    company.logo.save(storage_name, uploaded, save=True)

    log_action(
        request,
        "UPDATE",
        "Company",
        object_id=company.id,
        description=f"Company logo updated: {company.name}",
        company=company,
    )
    data = CompanySerializer(company, context={"request": request}).data
    data["logoUrl"] = data.get("logo_url")
    return Response(data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def company_branding(request):
    # If the request is unauthenticated, return 401 for clarity.
    if not request.user or not request.user.is_authenticated:
        return Response({"detail": "Authentication credentials were not provided or are invalid."}, status=status.HTTP_401_UNAUTHORIZED)

    company = _get_request_company(request)
    if not company:
        return Response({"detail": "No company context found."}, status=status.HTTP_403_FORBIDDEN)
    if not _can_read_company_branding(request, company):
        return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
    data = CompanySerializer(company, context={"request": request}).data
    data["logoUrl"] = data.get("logo_url")
    return Response(data)


@api_view(["POST", "DELETE"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def company_branding_logo(request):
    company = _get_request_company(request)
    if not company:
        return Response({"detail": "No company context found."}, status=status.HTTP_403_FORBIDDEN)
    if not _can_manage_company_branding(request, company):
        return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

    if request.method == "DELETE":
        if hasattr(company, "clear_logo_file"):
            try:
                company.clear_logo_file()
                company.save(update_fields=["logo", "updated_at"])
            except Exception:
                pass
        else:
            return Response({"detail": "Company logo feature not available for this tenant."}, status=status.HTTP_400_BAD_REQUEST)
        data = CompanySerializer(company, context={"request": request}).data
        data["logoUrl"] = data.get("logo_url")
        return Response(data)

    uploaded = request.FILES.get("logo")
    if not uploaded:
        return Response({"logo": ["No file was submitted."]}, status=status.HTTP_400_BAD_REQUEST)

    err = _company_logo_validation_error(uploaded)
    if err:
        return Response({"error": err}, status=status.HTTP_400_BAD_REQUEST)

    if not hasattr(company, "logo"):
        return Response({"detail": "Company logo feature not available for this tenant."}, status=status.HTTP_400_BAD_REQUEST)

    if getattr(company, "logo"):
        try:
            company.logo.delete(save=False)
        except Exception:
            pass

    ext = os.path.splitext(uploaded.name or "")[1].lower()
    if ext not in ALLOWED_LOGO_EXTENSIONS:
        ext = ".png"
    storage_name = f"{uuid.uuid4().hex}{ext}"
    company.logo.save(storage_name, uploaded, save=True)
    data = CompanySerializer(company, context={"request": request}).data
    data["logoUrl"] = data.get("logo_url")
    return Response(data)


@api_view(["DELETE"])
@permission_classes([IsSuperAdmin])
def company_delete(request, company_id):
    company = get_object_or_404(Company, id=company_id)
    # Soft delete: deactivate (Suspend)
    company.is_active = False
    company.save(update_fields=["is_active"])
    return Response({"message": "Company deactivated successfully"})


@api_view(["POST"])
@permission_classes([IsSuperAdmin])
def company_activate(request, company_id):
    company = get_object_or_404(Company, id=company_id)
    company.is_active = True
    company.save(update_fields=["is_active"])
    return Response({"message": "Company activated successfully"})


@api_view(["POST"])
@permission_classes([IsSuperAdmin])
def company_stop_actions(request, company_id):
    company = get_object_or_404(Company, id=company_id)
    company.billing_action_stopped = True
    company.save(update_fields=["billing_action_stopped"])
    log_action(
        request, "UPDATE", "Company",
        object_id=company.id,
        description=f"Stopped billing actions for company: {company.name}",
        company=company,
    )
    return Response({
        "message": "Company actions stopped successfully.",
        "company": CompanySerializer(company, context={"request": request}).data
    })


@api_view(["POST"])
@permission_classes([IsSuperAdmin])
def company_mark_paid(request, company_id):
    company = get_object_or_404(Company, id=company_id)
    # Default: extend subscription end date by 30 days from today
    today = timezone.now().date()
    new_end_date = today + timedelta(days=30)
    
    custom_date = request.data.get("subscription_period_end")
    if custom_date:
        try:
            from datetime import datetime
            new_end_date = datetime.strptime(custom_date, "%Y-%m-%d").date()
        except ValueError:
            pass

    company.subscription_period_end = new_end_date
    company.billing_action_stopped = False
    company.save(update_fields=["subscription_period_end", "billing_action_stopped"])
    
    log_action(
        request, "UPDATE", "Company",
        object_id=company.id,
        description=f"Marked company as paid and extended subscription to {new_end_date}: {company.name}",
        company=company,
    )
    return Response({
        "message": "Company marked as paid. Actions restored.",
        "company": CompanySerializer(company, context={"request": request}).data
    })


@api_view(["DELETE"])
@permission_classes([IsSuperAdmin])
def company_hard_delete(request, company_id):
    company = get_object_or_404(Company, id=company_id)
    company_name = company.name
    # Company model may no longer have a `logo` field after migrations.
    # Safely check before attempting to delete any file attribute.
    if hasattr(company, "logo") and getattr(company, "logo"):
        try:
            company.logo.delete(save=False)
        except Exception:
            # Ignore errors during file deletion to allow hard-delete to proceed
            pass

    # Remove dependent objects that reference this company to avoid FK constraint errors.
    from django.apps import apps
    from django.db import transaction, IntegrityError

    related_deletions = []
    try:
        with transaction.atomic():
            CompanyModel = apps.get_model("accounts", "Company")
            for model in apps.get_models():
                for field in model._meta.get_fields():
                    remote = getattr(field, "remote_field", None)
                    if not remote or not getattr(remote, "model", None):
                        continue
                    # remote.model may be a string or model class
                    try:
                        remote_model = remote.model
                    except Exception:
                        remote_model = None
                    if remote_model == CompanyModel or (isinstance(remote_model, str) and remote_model.endswith("Company")):
                        # Build filter by FK id
                        fk_name = field.name
                        filter_kwargs = {f"{fk_name}_id": company.id}
                        qs = model.objects.filter(**filter_kwargs)
                        count = qs.count()
                        if count:
                            qs.delete()
                            related_deletions.append((model._meta.label, count))
            # Finally delete the company record itself
            company.delete()
    except IntegrityError as exc:
        logger.exception("Failed to hard-delete company due to DB integrity error")
        # Attempt best-effort cleanup of DB-level foreign key references not exposed in Django models
        from django.db import connection
        cleaned_tables = []
        try:
            with transaction.atomic():
                cursor = connection.cursor()
                cursor.execute("SELECT DATABASE()")
                dbname = cursor.fetchone()[0]
                cursor.execute(
                    """
                    SELECT TABLE_NAME, COLUMN_NAME
                    FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
                    WHERE REFERENCED_TABLE_SCHEMA = %s AND REFERENCED_TABLE_NAME = %s
                    """,
                    [dbname, 'accounts_company'],
                )
                fks = cursor.fetchall()
                for table, column in fks:
                    if table == 'accounts_company':
                        continue
                    try:
                        cursor.execute(f"DELETE FROM `{table}` WHERE `{column}` = %s", [company.id])
                        cleaned_tables.append(table)
                    except Exception:
                        logger.exception("Failed deleting from %s.%s", table, column)
                # retry delete
                company.delete()
        except Exception:
            logger.exception("Best-effort DB cleanup failed")
            return Response({"error": "Failed to delete company due to related database records. Clean up dependencies first."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        msg = f"Company '{company_name}' permanently deleted"
        if cleaned_tables:
            msg += "; cleaned: " + ", ".join(sorted(set(cleaned_tables)))
        return Response({"message": msg})
    msg = f"Company '{company_name}' permanently deleted"
    if related_deletions:
        msg += "; removed related: " + ", ".join([f"{label}({cnt})" for label, cnt in related_deletions])
    return Response({"message": msg})


# =========================================================
# 📋 SIDEBAR MENU (ROLE BASED)
# =========================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sidebar_permissions(request):

    role = request.user.role

    menu = {
        "SUPER_ADMIN": ["Dashboard", "Manage Users", "System Settings"],
        "ADMIN": ["Dashboard", "Employees", "Attendance", "Payroll"],
        "HR": ["Dashboard", "Employees", "Leaves"],
        "EMPLOYEE": ["Dashboard", "My Attendance", "My Payslips"]
    }

    return Response({
        "role": role,
        "menu": menu.get(role, [])
    })


# =========================================================
# 🚪 LOGOUT (JWT BLACKLIST)
# =========================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):

    try:
        refresh_token = request.data.get("refresh")
        token = RefreshToken(refresh_token)
        token.blacklist()
        return Response({"message": "Logged out successfully"})
    except Exception:
        return Response(
            {"error": "Invalid token"},
            status=status.HTTP_400_BAD_REQUEST
        )


# =========================================================
# 🏠 ROOT
# =========================================================

@api_view(["GET"])
@permission_classes([AllowAny])
def accounts_root(request):
    return Response({
        "message": "Accounts API working",
        "available_endpoints": [
            "login/",
            "superadmin/users/",
            "change-password/",
            "analytics/",
        ]
    })

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):

    user = request.user

    data = {
        "id": user.id,
        "username": user.username,
        "role": user.role,
    }

    # If employee profile exists
    if hasattr(user, "employee_profile"):
        emp = user.employee_profile
        data.update({
            "employee_id": emp.employee_id,
            "first_name": emp.first_name,
            "last_name": emp.last_name,
            "company": emp.company.name if getattr(emp, "company", None) else None,
            "company_id": emp.company_id,
        })

    return Response(data)

# =========================================================
# 🏢 COMPANY SMTP SETTINGS
# =========================================================

from apps.accounts.email_utils import encrypt_smtp_password

@api_view(["GET", "PATCH"])
@permission_classes([IsCompanyAdminOrHR])
def company_smtp_settings(request):
    company = getattr(request.user, "company", None)
    if not company:
        return Response({"error": "No company associated with user"}, status=400)

    if request.method == "GET":
        data = {
            "use_company_smtp": company.use_company_smtp,
            "smtp_host": company.smtp_host or "",
            "smtp_port": company.smtp_port or 587,
            "smtp_username": company.smtp_username or "",
            "smtp_use_tls": company.smtp_use_tls,
            "from_email": company.from_email or "",
            "smtp_password_set": bool(company.smtp_password),
        }
        return Response(data)

    elif request.method == "PATCH":
        company.use_company_smtp = request.data.get("use_company_smtp", company.use_company_smtp)
        company.smtp_host = request.data.get("smtp_host", company.smtp_host)
        if "smtp_port" in request.data:
            company.smtp_port = request.data["smtp_port"]
        company.smtp_username = request.data.get("smtp_username", company.smtp_username)
        company.smtp_use_tls = request.data.get("smtp_use_tls", company.smtp_use_tls)
        company.from_email = request.data.get("from_email", company.from_email)
        
        new_password = request.data.get("smtp_password")
        if new_password:
            company.smtp_password = encrypt_smtp_password(new_password)
            
        company.save()
        log_action(request, "UPDATE", "Company", object_id=company.id, description="Updated Company SMTP settings", company=company)
        return Response({"message": "Settings updated successfully"})

@api_view(["POST"])
@permission_classes([IsCompanyAdminOrHR])
def company_smtp_test(request):
    company = getattr(request.user, "company", None)
    if not company:
        return Response({"error": "No company associated with user"}, status=400)
    
    to_email = request.data.get("to_email")
    if not to_email:
        return Response({"error": "to_email is required"}, status=400)
        
    from django.core.mail import EmailMultiAlternatives
    from apps.accounts.email_utils import get_company_email_connection
    
    subject = "Test SMTP Settings"
    text_content = "Your company-specific SMTP configuration works perfectly."
    from_email = company.from_email or "no-reply@company.com"
    
    try:
        connection = get_company_email_connection(company)
        msg = EmailMultiAlternatives(subject, text_content, from_email, [to_email], connection=connection)
        msg.send(fail_silently=False)
        return Response({"message": "Test email sent successfully"})
    except Exception as exc:
        return Response({"error": f"Failed to send test email. Please check your SMTP configuration.", "detail": str(exc)}, status=400)

