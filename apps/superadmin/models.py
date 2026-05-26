import secrets
import string
from datetime import timedelta
from django.db import models
from django.conf import settings
from django.contrib.auth.hashers import make_password, check_password
from django.utils import timezone


class SystemSetting(models.Model):
    """
    Key-value store for global platform settings.
    Grouped by category for UI display.
    """
    CATEGORY_GENERAL = "general"
    CATEGORY_EMAIL = "email"
    CATEGORY_SECURITY = "security"

    CATEGORY_CHOICES = [
        (CATEGORY_GENERAL, "General"),
        (CATEGORY_EMAIL, "Email"),
        (CATEGORY_SECURITY, "Security"),
    ]

    TYPE_STRING = "string"
    TYPE_BOOLEAN = "boolean"
    TYPE_INTEGER = "integer"

    TYPE_CHOICES = [
        (TYPE_STRING, "String"),
        (TYPE_BOOLEAN, "Boolean"),
        (TYPE_INTEGER, "Integer"),
    ]

    key = models.CharField(max_length=100, unique=True, db_index=True)
    value = models.TextField(blank=True, default="")
    label = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    category = models.CharField(
        max_length=20, choices=CATEGORY_CHOICES, default=CATEGORY_GENERAL, db_index=True
    )
    value_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_STRING)
    is_sensitive = models.BooleanField(default=False, help_text="Mask value in API responses")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["category", "key"]

    def __str__(self):
        return f"{self.category}/{self.key} = {self.value}"

    @property
    def typed_value(self):
        if self.value_type == self.TYPE_BOOLEAN:
            return self.value.lower() in ("true", "1", "yes")
        if self.value_type == self.TYPE_INTEGER:
            try:
                return int(self.value)
            except (ValueError, TypeError):
                return 0
        return self.value


class MfaOtpRecord(models.Model):
    """One-time password record for user MFA flow.

    Matches the migration `0002_mfaotprecord.py`.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mfa_otp_record",
    )
    otp_hash = models.CharField(max_length=256)
    expires_at = models.DateTimeField(db_index=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "MFA OTP Record"

    @property
    def is_expired(self) -> bool:
        return bool(self.expires_at and timezone.now() >= self.expires_at)

    @property
    def is_verified(self) -> bool:
        return self.verified_at is not None

    def matches(self, raw_otp: str) -> bool:
        return check_password(str(raw_otp), self.otp_hash)


def create_or_replace_otp(user, ttl_minutes: int = 10) -> str:
    """Generate a 6-digit OTP, store its hash on the user's MfaOtpRecord and return the raw OTP.

    If a record exists, it is overwritten so there's always a single active OTP per user.
    """
    raw = "".join(secrets.choice(string.digits) for _ in range(6))
    hashed = make_password(raw)
    expires = timezone.now() + timedelta(minutes=int(ttl_minutes))

    # Create or update the OneToOne record
    obj, _ = MfaOtpRecord.objects.update_or_create(
        user=user,
        defaults={
            "otp_hash": hashed,
            "expires_at": expires,
            "verified_at": None,
        },
    )
    return raw



