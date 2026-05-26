from django.db import models, transaction
from django.db.models import Count, Sum, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone
from django.core.mail import EmailMultiAlternatives
from django.conf import settings as django_settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from datetime import date, timedelta
from apps.accounts.permissions import IsSuperAdmin
from apps.accounts.models import User, Company
from apps.employees.models import Employee
from apps.leaves.models import LeaveRequest
from apps.payroll.models import Payslip
from apps.billing.models import Payment, Invoice, PricingPlan
from apps.audit.utils import log_action

from .models import SystemSetting, MfaOtpRecord, create_or_replace_otp
from .services import (
    get_bool_setting,
    get_effective_settings_payload,
    issue_token_pair_for_user,
    is_password_expired,
)


# ─────────────────────────────────────────
#  DEFAULT SETTINGS (seed on first access)
# ─────────────────────────────────────────

DEFAULT_SETTINGS = [
    # General
    {"key": "platform_name", "value": "HRMS Platform", "label": "Platform Name",
     "description": "Name displayed across the platform UI.", "category": "general", "value_type": "string"},
    {"key": "support_email", "value": "support@hrms.com", "label": "Support Email",
     "description": "Contact email shown to users.", "category": "general", "value_type": "string"},
    {"key": "default_timezone", "value": "Asia/Kolkata", "label": "Default Timezone",
     "description": "Platform default timezone.", "category": "general", "value_type": "string"},
    {"key": "maintenance_mode", "value": "false", "label": "Maintenance Mode",
     "description": "When enabled, only Super Admins can log in.", "category": "general", "value_type": "boolean"},

    # Email
    {"key": "smtp_host", "value": "", "label": "SMTP Host",
     "description": "Outgoing mail server hostname.", "category": "email", "value_type": "string"},
    {"key": "smtp_port", "value": "587", "label": "SMTP Port",
     "description": "Usually 587 (TLS) or 465 (SSL).", "category": "email", "value_type": "integer"},
    {"key": "smtp_username", "value": "", "label": "SMTP Username",
     "description": "SMTP authentication username.", "category": "email", "value_type": "string"},
    {"key": "smtp_password", "value": "", "label": "SMTP Password",
     "description": "SMTP authentication password.", "category": "email", "value_type": "string",
     "is_sensitive": True},
    {"key": "smtp_use_tls", "value": "true", "label": "Use TLS",
     "description": "Enable TLS encryption for email.", "category": "email", "value_type": "boolean"},
    {"key": "from_email", "value": "no-reply@hrms.com", "label": "From Email",
     "description": "Sender address for all outgoing emails.", "category": "email", "value_type": "string"},

    # Security
    {"key": "min_password_length", "value": "8", "label": "Minimum Password Length",
     "description": "Minimum characters required for passwords.", "category": "security", "value_type": "integer"},
    {"key": "session_timeout_minutes", "value": "60", "label": "Session Timeout (minutes)",
     "description": "Idle session expiry duration.", "category": "security", "value_type": "integer"},
    {"key": "max_login_attempts", "value": "5", "label": "Max Login Attempts",
     "description": "Account locks after this many failed logins.", "category": "security", "value_type": "integer"},
    {"key": "require_mfa", "value": "false", "label": "Require MFA",
     "description": "Enforce Multi-Factor Authentication for all users.", "category": "security", "value_type": "boolean"},
    {"key": "password_expiry_days", "value": "90", "label": "Password Expiry (days)",
     "description": "Force password reset after this many days (0 = never).", "category": "security", "value_type": "integer"},

]


def seed_default_settings():
    """Insert default settings if they don't exist."""
    for s in DEFAULT_SETTINGS:
        SystemSetting.objects.get_or_create(
            key=s["key"],
            defaults={
                "value": s["value"],
                "label": s["label"],
                "description": s.get("description", ""),
                "category": s["category"],
                "value_type": s["value_type"],
                "is_sensitive": s.get("is_sensitive", False),
            }
        )


def setting_to_dict(s):
    return {
        "key": s.key,
        "value": "" if s.is_sensitive and s.value else s.value,
        "label": s.label,
        "description": s.description,
        "category": s.category,
        "value_type": s.value_type,
        "is_sensitive": s.is_sensitive,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


# ─────────────────────────────────────────
#  SETTINGS VIEWS
# ─────────────────────────────────────────

@api_view(["GET"])
@permission_classes([IsSuperAdmin])
def settings_list(request):
    """GET /api/superadmin/settings/ — Return all settings grouped by category."""
    seed_default_settings()
    settings_qs = SystemSetting.objects.all()
    grouped = {}
    for s in settings_qs:
        grouped.setdefault(s.category, []).append(setting_to_dict(s))
    return Response(grouped)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def effective_settings(request):
    """Return settings that normal portals need to enforce locally."""
    seed_default_settings()
    company = getattr(request.user, "company", None)
    return Response(get_effective_settings_payload(company=company))


def _apply_smtp_to_django(settings_dict=None):
    """
    Apply SMTP settings from the database to Django's live email configuration.
    Called after every save so emails work immediately (no restart needed).
    """
    import django.core.mail as _mail
    from .services import get_setting_value, get_bool_setting, get_int_setting

    host     = (settings_dict or {}).get("smtp_host")     or get_setting_value("smtp_host", "")
    port     = (settings_dict or {}).get("smtp_port")     or get_setting_value("smtp_port", "587")
    user     = (settings_dict or {}).get("smtp_username") or get_setting_value("smtp_username", "")
    password = (settings_dict or {}).get("smtp_password") or get_setting_value("smtp_password", "")
    use_tls  = (settings_dict or {}).get("smtp_use_tls")  or get_setting_value("smtp_use_tls", "true")
    from_em  = (settings_dict or {}).get("from_email")    or get_setting_value("from_email", "no-reply@hrms.com")

    use_tls_bool = str(use_tls).strip().lower() in ("true", "1", "yes")
    try:
        port_int = int(str(port).strip())
    except (ValueError, TypeError):
        port_int = 587

    import os
    # Patch Django settings live (affects next email send in this process)
    django_settings.EMAIL_HOST          = host.strip() or os.getenv("EMAIL_HOST", "smtp.gmail.com")
    django_settings.EMAIL_PORT          = port_int
    django_settings.EMAIL_HOST_USER     = user.strip() or os.getenv("EMAIL_HOST_USER", "")
    django_settings.EMAIL_HOST_PASSWORD = password.strip() or os.getenv("EMAIL_HOST_PASSWORD", "")
    
    if port_int == 465:
        django_settings.EMAIL_USE_SSL = True
        django_settings.EMAIL_USE_TLS = False
    else:
        django_settings.EMAIL_USE_SSL = False
        django_settings.EMAIL_USE_TLS = use_tls_bool
        
    django_settings.DEFAULT_FROM_EMAIL  = from_em.strip() or "no-reply@hrms.com"

    # Force Django's mail module to pick up fresh connection on next send
    _mail.outbox = getattr(_mail, "outbox", [])  # noqa — only present in test mode


@api_view(["PATCH"])
@permission_classes([IsSuperAdmin])
def settings_update(request):
    """PATCH /api/superadmin/settings/update/ — Bulk update settings.
    Body: { "key": "value", ... }
    """
    updates = request.data
    if not isinstance(updates, dict):
        return Response({"error": "Expected a JSON object."}, status=status.HTTP_400_BAD_REQUEST)

    seed_default_settings()
    existing = {
        setting.key: setting
        for setting in SystemSetting.objects.filter(key__in=updates.keys())
    }
    unknown_keys = sorted(set(updates.keys()) - set(existing.keys()))
    if unknown_keys:
        return Response(
            {"error": "Unknown setting key(s).", "keys": unknown_keys},
            status=status.HTTP_400_BAD_REQUEST,
        )

    normalized_updates = {}
    for key, value in updates.items():
        setting = existing[key]
        if setting.is_sensitive and value in ("", None):
            continue
        if setting.value_type == SystemSetting.TYPE_BOOLEAN:
            if isinstance(value, bool):
                normalized_updates[key] = "true" if value else "false"
            elif str(value).strip().lower() in ("true", "1", "yes", "on"):
                normalized_updates[key] = "true"
            elif str(value).strip().lower() in ("false", "0", "no", "off"):
                normalized_updates[key] = "false"
            else:
                return Response(
                    {"error": f"{key} must be true or false."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        elif setting.value_type == SystemSetting.TYPE_INTEGER:
            try:
                normalized_updates[key] = str(int(value))
            except (TypeError, ValueError):
                return Response(
                    {"error": f"{key} must be an integer."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            normalized_updates[key] = str(value)

    with transaction.atomic():
        for key, value in normalized_updates.items():
            SystemSetting.objects.filter(key=key).update(value=value)

    # ── Apply SMTP settings live so emails work without server restart ──────
    _apply_smtp_to_django()

    return Response({"status": "ok", "updated": list(normalized_updates.keys())})


@api_view(["POST"])
@permission_classes([IsSuperAdmin])
def test_smtp_email(request):
    """
    POST /api/superadmin/settings/test-email/
    Body: { "to": "recipient@example.com" }
    Sends a test email using the currently saved SMTP settings to verify the config.
    """
    to_address = (request.data.get("to") or "").strip()
    if not to_address:
        return Response({"error": "Recipient email (to) is required."}, status=status.HTTP_400_BAD_REQUEST)

    # Apply latest DB settings before sending
    _apply_smtp_to_django()

    from_email   = django_settings.DEFAULT_FROM_EMAIL or "no-reply@hrms.com"
    subject      = "✅ HRMS SMTP Test — Configuration Verified"
    text_body    = (
        "This is a test email sent by the HRMS Super Admin to verify SMTP configuration.\n\n"
        "If you received this, your email settings are working correctly!"
    )
    html_body    = """
<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr><td align="center" style="padding:40px 16px;">
      <table width="520" cellpadding="0" cellspacing="0"
             style="background:#fff;border-radius:14px;overflow:hidden;box-shadow:0 4px 20px rgba(15,23,42,0.12);">
        <tr>
          <td style="background:linear-gradient(135deg,#1e3a8a,#2563eb);padding:28px 32px;text-align:center;">
            <div style="font-size:40px;margin-bottom:10px;">✅</div>
            <h1 style="margin:0;color:white;font-size:20px;font-weight:800;">SMTP Configuration Verified!</h1>
            <p style="margin:8px 0 0;color:rgba(255,255,255,0.8);font-size:14px;">HRMS Platform — Email Test</p>
          </td>
        </tr>
        <tr>
          <td style="padding:28px 32px;text-align:center;">
            <p style="margin:0;color:#374151;font-size:15px;line-height:1.7;">
              Your SMTP configuration is working correctly.<br>
              All system emails (MFA codes, notifications, payslips) will be delivered to users.
            </p>
            <div style="margin:20px 0;padding:14px 20px;background:#ecfdf5;border-radius:8px;border:1px solid #a7f3d0;">
              <p style="margin:0;color:#047857;font-size:14px;font-weight:600;">
                📬 Email delivered successfully from: <strong>""" + from_email + """</strong>
              </p>
            </div>
          </td>
        </tr>
        <tr>
          <td style="background:#f8fafc;padding:14px 32px;text-align:center;border-top:1px solid #e2e8f0;">
            <p style="margin:0;color:#94a3b8;font-size:12px;">This is an automated test from HRMS Platform.</p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body></html>
""".strip()

    try:
        msg = EmailMultiAlternatives(subject, text_body, from_email, [to_address])
        msg.attach_alternative(html_body, "text/html")
        msg.send(fail_silently=False)
        return Response({
            "status": "ok",
            "message": f"Test email sent successfully to {to_address}.",
            "from": from_email,
        })
    except Exception as exc:
        return Response({
            "error": "Failed to send test email.",
            "detail": str(exc),
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



# ─────────────────────────────────────────
#  REPORTS VIEW
# ─────────────────────────────────────────

@api_view(["GET"])
@permission_classes([IsSuperAdmin])
def reports_overview(request):
    """GET /api/superadmin/reports/ — Platform-wide KPI snapshot."""
    today = date.today()
    thirty_days_ago = today - timedelta(days=30)
    twelve_months_ago = today - timedelta(days=365)

    def add_months(year, month, delta):
        month_index = (year * 12 + month - 1) + delta
        return month_index // 12, month_index % 12 + 1

    def month_labels_for_last_12_months():
        labels = []
        start_year, start_month = add_months(today.year, today.month, -11)
        for offset in range(12):
            year, month = add_months(start_year, start_month, offset)
            labels.append(f"{year:04d}-{month:02d}")
        return labels

    def fill_month_series(rows, value_key):
        values = {
            row["month"].strftime("%Y-%m"): row[value_key] or 0
            for row in rows
            if row.get("month")
        }
        return [
            {
                "month": label,
                value_key: (
                    float(values.get(label, 0))
                    if value_key == "total"
                    else values.get(label, 0)
                ),
            }
            for label in month_labels_for_last_12_months()
        ]

    # ── KPI Cards ──────────────────────────────
    total_companies = Company.objects.count()
    active_companies = Company.objects.filter(is_active=True).count()
    total_users = User.objects.count()
    total_employees = Employee.objects.count()

    # New in last 30 days
    new_companies_30d = Company.objects.filter(created_at__date__gte=thirty_days_ago).count()
    new_users_30d = User.objects.filter(date_joined__date__gte=thirty_days_ago).count()

    # Billing
    total_revenue = Payment.objects.filter(status="COMPLETED").aggregate(
        total=Sum("amount")
    )["total"] or 0
    revenue_30d = Payment.objects.filter(
        status="COMPLETED", payment_date__gte=thirty_days_ago
    ).aggregate(total=Sum("amount"))["total"] or 0

    paid_invoices = Invoice.objects.filter(status="PAID").count()
    pending_invoices = Invoice.objects.filter(status__in=["SENT", "DRAFT"]).count()
    overdue_invoices = Invoice.objects.filter(status="OVERDUE").count()

    # Subscriptions expiring in 30 days
    expiring_soon = Company.objects.filter(
        subscription_period_end__isnull=False,
        subscription_period_end__lte=today + timedelta(days=30),
        subscription_period_end__gte=today,
        is_active=True,
    ).count()

    # ── Monthly growth (12 months) ────────────
    monthly_companies = list(
        Company.objects
        .filter(created_at__date__gte=twelve_months_ago)
        .annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(count=Count("id"))
        .order_by("month")
    )
    monthly_users = list(
        User.objects
        .filter(date_joined__date__gte=twelve_months_ago)
        .annotate(month=TruncMonth("date_joined"))
        .values("month")
        .annotate(count=Count("id"))
        .order_by("month")
    )
    monthly_revenue = list(
        Payment.objects
        .filter(status="COMPLETED", payment_date__gte=twelve_months_ago)
        .annotate(month=TruncMonth("payment_date"))
        .values("month")
        .annotate(total=Sum("amount"))
        .order_by("month")
    )

    # ── Users by role breakdown ────────────────
    users_by_role = list(
        User.objects.values("role").annotate(count=Count("id")).order_by("-count")
    )

    # ── Top companies by employee count ───────
    top_companies = list(
        Company.objects
        .annotate(employee_count=Count("users", filter=Q(users__role='EMPLOYEE')))
        .filter(is_active=True)
        .order_by("-employee_count")[:10]
        .values("id", "name", "company_code", "employee_count", "subscription_period_end")
    )

    # ── Plan distribution ─────────────────────
    # Company.pricing_plan was removed from the model in recent migrations.
    # Derive plan distribution from completed Payments (pricing_plan used on Payment).
    plan_distribution = list(
        Payment.objects
        .filter(status="COMPLETED", pricing_plan__isnull=False)
        .values("pricing_plan__name")
        .annotate(count=Count("pricing_plan__name"))
        .order_by("-count")
    )

    # ── Recent payments ───────────────────────
    recent_payments = list(
        Payment.objects
        .select_related("company", "pricing_plan")
        .filter(status="COMPLETED")
        .order_by("-created_at")[:5]
        .values(
            "id", "amount", "currency", "payment_date", "status",
            "company__name", "company__company_code",
            "pricing_plan__name",
        )
    )

    return Response({
        "kpis": {
            "total_companies": total_companies,
            "active_companies": active_companies,
            "total_users": total_users,
            "total_employees": total_employees,
            "new_companies_30d": new_companies_30d,
            "new_users_30d": new_users_30d,
            "total_revenue": float(total_revenue),
            "revenue_30d": float(revenue_30d),
            "paid_invoices": paid_invoices,
            "pending_invoices": pending_invoices,
            "overdue_invoices": overdue_invoices,
            "expiring_soon": expiring_soon,
        },
        "monthly_companies": fill_month_series(monthly_companies, "count"),
        "monthly_users": fill_month_series(monthly_users, "count"),
        "monthly_revenue": fill_month_series(monthly_revenue, "total"),
        "users_by_role": users_by_role,
        "top_companies": top_companies,
        "plan_distribution": plan_distribution,
        "recent_payments": recent_payments,
    })


# ─────────────────────────────────────────
#  MONTHLY GROWTH (existing, kept)
# ─────────────────────────────────────────

@api_view(["GET"])
@permission_classes([IsSuperAdmin])
def monthly_growth_analytics(request):
    users = (
        User.objects
        .annotate(month=TruncMonth("date_joined"))
        .values("month")
        .annotate(count=Count("id"))
        .order_by("month")
    )
    employees = (
        Employee.objects
        .annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(count=Count("id"))
        .order_by("month")
    )
    leaves = (
        LeaveRequest.objects
        .annotate(month=TruncMonth("applied_on"))
        .values("month")
        .annotate(count=Count("id"))
        .order_by("month")
    )
    payslips = (
        Payslip.objects
        .annotate(month=TruncMonth("month"))
        .values("month")
        .annotate(count=Count("id"))
        .order_by("month")
    )
    return Response({
        "users": list(users),
        "employees": list(employees),
        "leaves": list(leaves),
        "payslips": list(payslips),
    })


# ─────────────────────────────────────────
#  MFA HELPERS
# ─────────────────────────────────────────

def _is_mfa_required() -> bool:
    """Return True if the platform-level require_mfa setting is 'true'."""
    return get_bool_setting("require_mfa", False)


def _send_mfa_otp_email(user, raw_otp: str):
    """Send the 6-digit OTP to the user's email address."""
    subject = "HRMS — Your Login Verification Code"
    display_name = user.get_full_name() or user.username or user.email
    text_content = (
        f"Hello {display_name},\n\n"
        f"Your HRMS login verification code is:\n\n"
        f"  {raw_otp}\n\n"
        f"This code expires in 10 minutes.\n\n"
        f"If you did not attempt to log in, please contact support immediately.\n\n"
        f"Regards,\nHRMS Security Team"
    )
    html_content = f"""
<div style="font-family:Arial,sans-serif;padding:24px;color:#111827;max-width:480px">
  <h2 style="color:#1e3a8a;margin-bottom:8px">🔐 Login Verification</h2>
  <p>Hello <strong>{display_name}</strong>,</p>
  <p>Use the 6-digit code below to complete your login:</p>
  <div style="font-size:36px;font-weight:900;letter-spacing:8px;background:#f3f4f6;
              padding:20px 28px;border-radius:12px;display:inline-block;
              color:#1e3a8a;margin:12px 0;">
    {raw_otp}
  </div>
  <p style="color:#6b7280;font-size:13px;">⏳ This code expires in <strong>10 minutes</strong>.</p>
  <p style="color:#dc2626;font-size:13px;">
    If you did not attempt to log in, please contact support immediately.
  </p>
  <p>Regards,<br><strong>HRMS Security Team</strong></p>
</div>
""".strip()

    from_email = getattr(django_settings, "DEFAULT_FROM_EMAIL", "no-reply@hrms.com")
    
    _apply_smtp_to_django()
    from django.core.mail import get_connection
    with get_connection() as connection:
        msg = EmailMultiAlternatives(subject, text_content, from_email, [user.email], connection=connection)
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=False)


# ─────────────────────────────────────────
#  MFA VIEWS
# ─────────────────────────────────────────

@api_view(["POST"])
@permission_classes([AllowAny])
def mfa_send_otp(request):
    """
    POST /api/superadmin/mfa/send/
    Body: { "user_id": 123 }
    Called immediately after successful password verification when MFA is required.
    Generates + emails a 6-digit OTP.
    """
    user_id = request.data.get("user_id")
    if not user_id:
        return Response({"error": "user_id is required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.get(id=user_id, is_active=True)
    except User.DoesNotExist:
        return Response({"error": "Invalid user."}, status=status.HTTP_400_BAD_REQUEST)

    raw_otp = create_or_replace_otp(user)

    try:
        _send_mfa_otp_email(user, raw_otp)
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Failed to send MFA OTP to %s", user.email)
        return Response(
            {"error": "Failed to send OTP email. Please check SMTP settings."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    masked_email = _mask_email(user.email)
    return Response({
        "message": f"Verification code sent to {masked_email}",
        "masked_email": masked_email,
    })


@api_view(["POST"])
@permission_classes([AllowAny])
def mfa_verify_otp(request):
    """
    POST /api/superadmin/mfa/verify/
    Body: { "user_id": 123, "otp": "123456" }
    Verifies OTP and if correct returns JWT tokens (completing the login).
    """
    user_id = request.data.get("user_id")
    raw_otp = str(request.data.get("otp", "")).strip()

    if not user_id or not raw_otp:
        return Response(
            {"error": "user_id and otp are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        user = User.objects.get(id=user_id, is_active=True)
    except User.DoesNotExist:
        return Response({"error": "Invalid user."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        record = MfaOtpRecord.objects.get(user=user)
    except MfaOtpRecord.DoesNotExist:
        return Response(
            {"error": "No OTP found. Please restart the login process."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if record.is_expired:
        return Response(
            {"error": "OTP has expired. Please restart the login process."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if record.is_verified:
        return Response(
            {"error": "OTP already used. Please restart the login process."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not record.matches(raw_otp):
        return Response(
            {"error": "Invalid verification code. Please try again."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # ✅ Mark as verified
    record.verified_at = timezone.now()
    record.save(update_fields=["verified_at"])

    # Issue JWT tokens now that MFA is complete
    access_token, refresh_token = issue_token_pair_for_user(user)

    log_action(
        request, "MFA_VERIFIED", "User",
        object_id=user.id,
        description=f"MFA verification successful for {user.email}",
        company=getattr(user, "company", None),
        user_override=user,
    )

    from apps.accounts.views import _build_auth_user_payload
    user_payload = _build_auth_user_payload(user, request)

    return Response({
        "access": access_token,
        "refresh": refresh_token,
        "force_password_change": (
            getattr(user, "must_change_password", False)
            or is_password_expired(user)
        ),
        "user": user_payload,
    })


def _mask_email(email: str) -> str:
    """Mask most of the email address for display: te***@gmail.com"""
    if "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        return f"{'*' * len(local)}@{domain}"
    return f"{local[:2]}{'*' * (len(local) - 2)}@{domain}"
