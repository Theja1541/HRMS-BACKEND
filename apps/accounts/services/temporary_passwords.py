import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone

from apps.accounts.models import TemporaryPasswordRecord


logger = logging.getLogger(__name__)

TEMP_PASSWORD_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789"


class TemporaryPasswordError(Exception):
    pass


class TemporaryPasswordEmailError(TemporaryPasswordError):
    pass


class TemporaryPasswordExpiredError(TemporaryPasswordError):
    pass


class TemporaryPasswordConsumedError(TemporaryPasswordError):
    pass


class TemporaryPasswordInvalidatedError(TemporaryPasswordError):
    pass


def get_temporary_password_expiry():
    expiry_hours = max(int(getattr(settings, "TEMP_PASSWORD_EXPIRY_HOURS", 24)), 1)
    return timezone.now() + timedelta(hours=expiry_hours)


def generate_temporary_password(length=12):
    return "".join(secrets.choice(TEMP_PASSWORD_ALPHABET) for _ in range(length))


def get_login_url():
    frontend_base_url = getattr(settings, "FRONTEND_BASE_URL", "http://localhost:5173")
    return f"{frontend_base_url.rstrip('/')}/login"


def ensure_email_configuration():
    required_settings = {
        "EMAIL_HOST": getattr(settings, "EMAIL_HOST", None),
        "EMAIL_HOST_USER": getattr(settings, "EMAIL_HOST_USER", None),
        "EMAIL_HOST_PASSWORD": getattr(settings, "EMAIL_HOST_PASSWORD", None),
        "DEFAULT_FROM_EMAIL": getattr(settings, "DEFAULT_FROM_EMAIL", None),
    }
    missing = [key for key, value in required_settings.items() if not value]
    if missing:
        raise TemporaryPasswordEmailError(
            "Email delivery is not configured correctly. Missing: "
            + ", ".join(sorted(missing))
        )


def build_temporary_password_email(user, temp_password, purpose, recipient_name=None):
    display_name = recipient_name or user.get_full_name() or user.username or user.email
    login_url = get_login_url()
    expiry_hours = max(int(getattr(settings, "TEMP_PASSWORD_EXPIRY_HOURS", 24)), 1)
    company_name = user.company.name if getattr(user, "company", None) else "HRMS"

    if purpose == TemporaryPasswordRecord.PURPOSE_PASSWORD_RESET:
        heading = "Temporary Password"
        subject = "HRMS - Temporary Password"
        intro = "A password reset was requested for your HRMS account."
    else:
        heading = "Your HRMS Company Portal Access"
        subject = "Your HRMS Company Portal Access"
        intro = f"Your HRMS account has been created successfully for {company_name}."

    text_content = f"""
Hello {display_name},

{intro}

Company: {company_name}
Login email: {user.email}
Temporary password: {temp_password}

This temporary password will expire in {expiry_hours} hour(s) or immediately after your first successful login.

HRMS login URL: {login_url}

Please sign in with the email and temporary password above, then change your password when prompted.

Regards,
HRMS Team
""".strip()

    html_content = f"""
<div style="font-family: Arial, sans-serif; padding: 20px; color: #111827;">
  <h2>{heading}</h2>
  <p>Hello <strong>{display_name}</strong>,</p>
  <p>{intro}</p>
  <p><strong>Company:</strong> {company_name}</p>
  <p><strong>Login email:</strong> <code style="background: #f3f4f6; padding: 4px 8px; border-radius: 4px;">{user.email}</code></p>
  <p><strong>Temporary password:</strong></p>
  <p style="font-size: 20px; font-weight: 700; letter-spacing: 1px; background: #f3f4f6; padding: 12px 16px; border-radius: 8px; display: inline-block;">
    {temp_password}
  </p>
  <p>This temporary password will expire in <strong>{expiry_hours} hour(s)</strong> or immediately after your first successful login.</p>
  <p><strong>HRMS login URL:</strong> <a href="{login_url}">{login_url}</a></p>
  <p>
    <a href="{login_url}" style="background: #2563eb; color: #ffffff; padding: 12px 20px; text-decoration: none; border-radius: 8px; display: inline-block;">
      Login to HRMS
    </a>
  </p>
  <p>Please sign in and change your password when prompted.</p>
  <p>Regards,<br><strong>HRMS Team</strong></p>
</div>
""".strip()

    return subject, text_content, html_content


def send_temporary_password_email(user, temp_password, purpose, recipient_name=None):
    ensure_email_configuration()

    subject, text_content, html_content = build_temporary_password_email(
        user=user,
        temp_password=temp_password,
        purpose=purpose,
        recipient_name=recipient_name,
    )

    email_message = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    email_message.attach_alternative(html_content, "text/html")
    email_message.send(fail_silently=False)


def save_temporary_password(user, temp_password, purpose, issued_by=None):
    user.set_password(temp_password)
    # `password_changed_at` field was removed from the User model in recent migrations.
    # Do not set or include it in update_fields to avoid ValueError on save().
    user.must_change_password = True
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

    record, _ = TemporaryPasswordRecord.objects.update_or_create(
        user=user,
        defaults={
            "password_hash": user.password,
            "purpose": purpose,
            "expires_at": get_temporary_password_expiry(),
            "first_login_at": None,
            "invalidated_at": None,
            "email_sent_at": timezone.now(),
            "created_by": issued_by,
        },
    )
    return record


def issue_and_send_temporary_password(user, purpose, issued_by=None, recipient_name=None):
    temp_password = generate_temporary_password()

    try:
        send_temporary_password_email(
            user=user,
            temp_password=temp_password,
            purpose=purpose,
            recipient_name=recipient_name,
        )
    except Exception as exc:
        logger.exception(
            "Failed to send temporary password email to user %s (%s)",
            user.pk,
            user.email,
        )
        if isinstance(exc, TemporaryPasswordEmailError):
            raise
        raise TemporaryPasswordEmailError(
            "Unable to send the temporary password email. Please verify SMTP settings and try again."
        ) from exc

    record = save_temporary_password(
        user=user,
        temp_password=temp_password,
        purpose=purpose,
        issued_by=issued_by,
    )
    return temp_password, record


def get_temporary_password_record(user):
    return TemporaryPasswordRecord.objects.filter(user=user).first()


def get_matching_temporary_password_record(user, raw_password):
    record = get_temporary_password_record(user)
    if record is None:
        return None

    if not record.matches(raw_password):
        return None

    return record


def validate_temporary_password_login(user, raw_password):
    record = get_matching_temporary_password_record(user, raw_password)
    if record is None:
        return None

    if record.is_invalidated:
        raise TemporaryPasswordInvalidatedError(
            "Temporary password is no longer valid. Please request a new one."
        )

    if record.is_consumed:
        raise TemporaryPasswordConsumedError(
            "Temporary password has already been used. Please change your password or request a new one."
        )

    if record.is_expired:
        raise TemporaryPasswordExpiredError(
            "Temporary password has expired. Please request a new one."
        )

    return record


def consume_temporary_password(record):
    if record and record.first_login_at is None:
        record.first_login_at = timezone.now()
        record.save(update_fields=["first_login_at", "updated_at"])


def invalidate_temporary_password(user):
    record = get_temporary_password_record(user)
    if record is None:
        return

    if record.invalidated_at is None:
        record.invalidated_at = timezone.now()
        record.save(update_fields=["invalidated_at", "updated_at"])
