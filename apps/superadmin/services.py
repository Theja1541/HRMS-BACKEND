from datetime import timedelta

from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from .models import SystemSetting


DEFAULT_SETTING_VALUES = {
    "platform_name": "HRMS Platform",
    "support_email": "support@hrms.com",
    "default_timezone": "Asia/Kolkata",
    "maintenance_mode": "false",
    "smtp_host": "",
    "smtp_port": "587",
    "smtp_username": "",
    "smtp_password": "",
    "smtp_use_tls": "true",
    "from_email": "no-reply@hrms.com",
    "min_password_length": "8",
    "session_timeout_minutes": "60",
    "max_login_attempts": "5",
    "require_mfa": "false",
    "password_expiry_days": "90",
}

FEATURE_FLAG_KEYS = {
    "leave": "enable_leave_module",
    "payroll": "enable_payroll_module",
    "assets": "enable_asset_module",
    "attendance": "enable_attendance_module",
    "support": "enable_support_tickets",
    "notifications": "enable_notifications_module",
    "billing": "enable_billing_module",
    "holidays": "enable_holiday_module",
    "daybook": "enable_daybook_module",
}


def get_setting_value(key, default=None):
    fallback = DEFAULT_SETTING_VALUES.get(key, default)
    try:
        return SystemSetting.objects.only("value").get(key=key).value
    except Exception:
        return fallback


def get_bool_setting(key, default=False):
    value = get_setting_value(key, "true" if default else "false")
    return str(value).strip().lower() in {"true", "1", "yes", "on"}


def get_int_setting(key, default=0, minimum=None, maximum=None):
    try:
        value = int(get_setting_value(key, default))
    except (TypeError, ValueError):
        value = default
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def is_module_enabled(module_name, company=None):
    if company is not None and isinstance(getattr(company, "enabled_modules", None), dict):
        val = company.enabled_modules.get(module_name)
        if val is None:
            return True
        if isinstance(val, bool):
            return val
        if isinstance(val, dict):
            if "enabled" in val:
                return val.get("enabled") is True
            return any(v is True for v in val.values())
    return True


def get_effective_settings_payload(company=None):
    return {
        "features": {
            module: is_module_enabled(module, company=company)
            for module in FEATURE_FLAG_KEYS
        },
        "company_enabled_modules": company.enabled_modules if company else {},
        "security": {
            "require_mfa": get_bool_setting("require_mfa", False),
            "min_password_length": get_int_setting("min_password_length", 8, minimum=1),
            "max_login_attempts": get_int_setting("max_login_attempts", 5, minimum=0),
            "session_timeout_minutes": get_int_setting(
                "session_timeout_minutes", 60, minimum=1, maximum=525600
            ),
            "password_expiry_days": get_int_setting(
                "password_expiry_days", 90, minimum=0
            ),
        },
    }


def validate_password_against_settings(password):
    min_length = get_int_setting("min_password_length", 8, minimum=1)
    if len(password or "") < min_length:
        return f"Password must be at least {min_length} characters."
    return None


def is_password_expired(user):
    days = get_int_setting("password_expiry_days", 90, minimum=0)
    if days <= 0:
        return False
    changed_at = getattr(user, "password_changed_at", None) or getattr(
        user, "created_at", None
    )
    if not changed_at:
        return False
    return changed_at <= timezone.now() - timedelta(days=days)


def issue_token_pair_for_user(user):
    refresh = RefreshToken.for_user(user)
    access = refresh.access_token
    timeout_minutes = get_int_setting("session_timeout_minutes", 60, minimum=1, maximum=525600)
    
    access.set_exp(lifetime=timedelta(minutes=timeout_minutes))
    refresh.set_exp(lifetime=timedelta(minutes=timeout_minutes))
    
    return str(access), str(refresh)
