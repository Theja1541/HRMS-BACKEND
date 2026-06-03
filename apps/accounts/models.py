from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator
from django.conf import settings

def company_logo_upload_to(instance, filename):
    return f"company_logos/company_{instance.id}/{filename}"

class User(AbstractUser):
    # Link user to a tenant company
    company = models.ForeignKey('Company', on_delete=models.SET_NULL, null=True, blank=True, related_name='users')

    ROLE_CHOICES = (
        ("SUPER_ADMIN", "Super Admin"),
        ("ADMIN", "Admin"),
        ("HR", "HR"),
        ("FINANCE_ADMIN", "Finance Admin"),
        ("EMPLOYEE", "Employee"),
    )

    phone_validator = RegexValidator(
        regex=r'^\+?\d{9,15}$',
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
    )

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default="EMPLOYEE",
        db_index=True
    )

    phone = models.CharField(
        validators=[phone_validator],
        max_length=15,
        blank=True
    )

    must_change_password = models.BooleanField(default=True)
    subscription_period_end = models.DateField(null=True, blank=True)
    billing_action_stopped = models.BooleanField(default=False, db_index=True)

    # Dynamic JSON Configurations
    departments = models.JSONField(default=list, blank=True)
    custom_roles = models.JSONField(default=list, blank=True)
    work_calendar = models.JSONField(default=dict, blank=True)
    hr_permissions = models.JSONField(default=dict, blank=True, null=True)
    hr_details = models.JSONField(default=dict, blank=True, null=True)
    failed_attempts = models.IntegerField(default=0)
    is_locked = models.BooleanField(default=False, db_index=True)
    locked_at = models.DateTimeField(null=True, blank=True)

    # Enterprise HR Details and Onboarding Documents
    employee_id = models.CharField(max_length=50, blank=True, null=True)
    profile_photo = models.ImageField(upload_to="hr/photos/", blank=True, null=True)
    resume = models.FileField(upload_to="hr/documents/", blank=True, null=True)
    offer_letter = models.FileField(upload_to="hr/documents/", blank=True, null=True)
    aadhar_card = models.FileField(upload_to="hr/documents/", blank=True, null=True)
    pan_card = models.FileField(upload_to="hr/documents/", blank=True, null=True)
    address_proof = models.FileField(upload_to="hr/documents/", blank=True, null=True)
    education_certificate = models.FileField(upload_to="hr/documents/", blank=True, null=True)
    experience_certificate = models.FileField(upload_to="hr/documents/", blank=True, null=True)

    def __str__(self):
        return f"{self.username} ({self.role})"
    # from teja


def default_enabled_modules():
    return {
        "attendance": True,
        "leave": True,
        "payroll": True,
        "assets": True,
        "support": True,
        "notifications": True,
        "billing": True,
        "daybook": True,
        "holidays": True,
    }

class Company(models.Model):
    """Multi-tenant company entity storing core configuration and branding."""
    
    enabled_modules = models.JSONField(default=default_enabled_modules, blank=True)
    # name = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=255)
    company_code = models.CharField(max_length=50, unique=True, help_text="Unique code or short identifier for the company")
    domain = models.CharField(max_length=255, blank=True, null=True, help_text="Custom domain or subdomain for white-labeling")
    logo = models.ImageField(upload_to="company_logos/", null=True, blank=True)
    email = models.EmailField(blank=True, null=True, help_text="Company contact email")
    address = models.TextField(blank=True, default="")
    phone = models.CharField(max_length=20, blank=True, default="")
    gstin = models.CharField(max_length=50, blank=True, default="")
    state = models.CharField(max_length=100, blank=True, default="")
    state_code = models.CharField(max_length=100, blank=True, default="")
    bank_account_no = models.CharField(max_length=50, blank=True, default="")
    bank_ifsc = models.CharField(max_length=20, blank=True, default="")
    bank_branch = models.CharField(max_length=100, blank=True, default="")
    

    is_active = models.BooleanField(default=True, db_index=True)
    billing_action_stopped = models.BooleanField(default=False, db_index=True)
    subscription_period_end = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.company_code})"


class TemporaryPasswordRecord(models.Model):
    """Tracks temporary passwords issued for onboarding or password reset."""

    PURPOSE_ONBOARDING = "ONBOARDING"
    PURPOSE_PASSWORD_RESET = "PASSWORD_RESET"

    PURPOSE_CHOICES = (
        (PURPOSE_ONBOARDING, "Onboarding"),
        (PURPOSE_PASSWORD_RESET, "Password Reset"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="temporary_password_records",
    )
    password_hash = models.CharField(max_length=128)
    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES)
    expires_at = models.DateTimeField()
    first_login_at = models.DateTimeField(null=True, blank=True)
    invalidated_at = models.DateTimeField(null=True, blank=True)
    email_sent_at = models.DateTimeField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_temp_passwords",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"TempPwd for {self.user.username} ({self.purpose})"

    def matches(self, raw_password):
        from django.contrib.auth.hashers import check_password
        return check_password(raw_password, self.password_hash)

    @property
    def is_invalidated(self):
        return self.invalidated_at is not None

    @property
    def is_consumed(self):
        return self.first_login_at is not None

    @property
    def is_expired(self):
        from django.utils import timezone
        return timezone.now() > self.expires_at
