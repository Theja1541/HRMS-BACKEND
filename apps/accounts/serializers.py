from django.contrib.auth import authenticate, get_user_model
from django.utils import timezone
from rest_framework import serializers

from .models import User, Company
from apps.billing.models import Payment
from apps.superadmin.services import (
    get_int_setting,
    validate_password_against_settings,
)


class CompanySerializer(serializers.ModelSerializer):
    logo_url = serializers.SerializerMethodField()
    employee_count = serializers.IntegerField(read_only=True, required=False)
    pricing_plan_id = serializers.SerializerMethodField()
    pricing_plan_name = serializers.SerializerMethodField()
    pricing_plan_price_monthly = serializers.SerializerMethodField()
    subscription_period_start = serializers.SerializerMethodField()
    # pricing_plan and logo fields were removed from the Company model in recent migrations.
    # Keep only fields that exist on the model and computed `employee_count`.

    class Meta:
        model = Company
        fields = [
            "id",
            "name",
            "company_code",
            "domain",
            # Removed deprecated contact/plan fields to match model
            "is_active",
            "created_at",
            "updated_at",
            "employee_count",
            "subscription_period_end",
            "subscription_period_start",
            "pricing_plan_id",
            "pricing_plan_name",
            "pricing_plan_price_monthly",
            "billing_action_stopped",
            "logo_url",
            "enabled_modules",
            "address",
            "phone",
            "gstin",
            "state",
            "state_code",
            "bank_account_no",
            "bank_ifsc",
            "bank_branch",
        ]
        read_only_fields = [
            "created_at",
            "updated_at",
            "employee_count",
            # read-only computed fields
        ]
    # Note: logo handling removed because Company model no longer stores a logo file.

    def get_logo_url(self, obj):
        if hasattr(obj, "logo") and getattr(obj, "logo") and hasattr(obj.logo, "url"):
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.logo.url)
            return obj.logo.url
        return None

    def _latest_pricing_payment(self, company):
        # Return the most recent Payment that references a pricing_plan for this company
        try:
            return (
                Payment.objects.select_related("pricing_plan")
                .filter(company=company, pricing_plan__isnull=False)
                .order_by("-created_at")
                .first()
            )
        except Exception:
            return None

    def get_pricing_plan_id(self, obj):
        p = self._latest_pricing_payment(obj)
        return p.pricing_plan.id if p and p.pricing_plan else None

    def get_pricing_plan_name(self, obj):
        p = self._latest_pricing_payment(obj)
        return p.pricing_plan.name if p and p.pricing_plan else None

    def get_pricing_plan_price_monthly(self, obj):
        p = self._latest_pricing_payment(obj)
        if p and p.pricing_plan:
            return str(p.pricing_plan.price_monthly)
        return None

    def get_subscription_period_start(self, obj):
        # We don't store subscription_period_start on Company; infer from latest payment_date if present
        p = self._latest_pricing_payment(obj)
        if p and p.payment_date:
            return p.payment_date.isoformat()
        return None
from .services.temporary_passwords import (
    TemporaryPasswordConsumedError,
    TemporaryPasswordExpiredError,
    TemporaryPasswordInvalidatedError,
    validate_temporary_password_login,
)


class CreateUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        trim_whitespace=False,
    )

    class Meta:
        model = User
        fields = ["username", "email", "password", "role", "first_name", "last_name"]

    def validate(self, attrs):
        role = str(attrs.get("role") or "").upper().strip()
        email = str(attrs.get("email") or "").strip().lower()
        username = str(attrs.get("username") or "").strip()
        password = attrs.get("password") or ""
        valid_roles = {choice[0] for choice in User.ROLE_CHOICES}

        if role not in valid_roles:
            raise serializers.ValidationError(
                {"role": "Invalid role selected."}
            )

        if not email:
            raise serializers.ValidationError(
                {"email": "Email is required."}
            )

        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError(
                {"email": "A user with this email already exists."}
            )

        attrs["role"] = role
        attrs["email"] = email
        attrs["username"] = username or email

        # Company Admin and HR onboarding use a generated temporary password by email.
        if role in {"ADMIN", "HR"}:
            attrs.pop("password", None)
            return attrs

        if not password:
            raise serializers.ValidationError(
                {"password": "Password is required for this role."}
            )

        password_error = validate_password_against_settings(password)
        if password_error:
            raise serializers.ValidationError(
                {"password": password_error}
            )

        return attrs

    def create(self, validated_data, **kwargs):
        password = validated_data.pop("password", None)
        company = kwargs.pop("company", None)
        user = User(**validated_data)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.must_change_password = False
        user.failed_attempts = 0
        user.is_locked = False
        user.locked_at = None
        # Tenant Admin (and any API-created user) must NOT have Django admin access
        user.is_superuser = False
        user.is_staff = False
        if company is not None:
            user.company = company
        user.save()
        return user


class UserSerializer(serializers.ModelSerializer):
    company_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "role",
            "company",
            "company_name",
            "phone",
            "must_change_password",
            "is_locked",
            "is_active",
            "date_joined",
        ]

    def get_company_name(self, obj):
        return obj.company.name if getattr(obj, "company", None) else None


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        email = data.get("email")
        password = data.get("password")

        user_model = get_user_model()

        try:
            user = user_model.objects.get(email=email)
        except user_model.DoesNotExist:
            raise serializers.ValidationError(
                {"email": "No account found with this email"}
            )
        except user_model.MultipleObjectsReturned:
            raise serializers.ValidationError(
                {"email": "Multiple accounts exist with this email. Please contact support."}
            )

        from apps.superadmin.services import get_bool_setting
        if get_bool_setting("maintenance_mode", False) and getattr(user, "role", "") != "SUPER_ADMIN":
            from django.core.mail import get_connection, EmailMultiAlternatives
            from django.conf import settings as django_settings
            from apps.superadmin.views import _apply_smtp_to_django
            
            try:
                _apply_smtp_to_django()
                with get_connection() as connection:
                    subject = "HRMS - Maintenance Mode"
                    text_content = "Hello,\n\nThe HRMS Application is currently in Maintenance Mode. Please try again after sometime.\n\nRegards,\nHRMS Team"
                    from_email = getattr(django_settings, "DEFAULT_FROM_EMAIL", "no-reply@hrms.com")
                    msg = EmailMultiAlternatives(subject, text_content, from_email, [user.email], connection=connection)
                    msg.send(fail_silently=True)
            except Exception:
                pass
            raise serializers.ValidationError(
                {"detail": "Application is in Maintenance Mode. Please try after sometime."}
            )

        if user.is_locked:
            raise serializers.ValidationError(
                {"detail": "Account is locked. Contact admin."}
            )

        authenticated_user = authenticate(
            username=user.username,
            password=password,
        )

        if not authenticated_user:
            user.failed_attempts += 1

            max_failed_attempts = get_int_setting(
                "max_login_attempts", 5, minimum=0
            )
            if max_failed_attempts > 0 and user.failed_attempts >= max_failed_attempts:
                user.is_locked = True
                user.locked_at = timezone.now()

            user.save(update_fields=["failed_attempts", "is_locked", "locked_at"])

            raise serializers.ValidationError(
                {"password": "Invalid password"}
            )

        if not user.is_active:
            raise serializers.ValidationError(
                {"detail": "User is inactive"}
            )

        try:
            temporary_password_record = validate_temporary_password_login(
                user=user,
                raw_password=password,
            )
        except (
            TemporaryPasswordConsumedError,
            TemporaryPasswordExpiredError,
            TemporaryPasswordInvalidatedError,
        ) as exc:
            raise serializers.ValidationError({"password": str(exc)}) from exc

        user.failed_attempts = 0
        user.is_locked = False
        user.locked_at = None
        user.save(update_fields=["failed_attempts", "is_locked", "locked_at"])

        data["user"] = user
        data["temporary_password_record"] = temporary_password_record
        return data

# ===========================
# UPDATE ROLE
# ===========================
class UpdateUserRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["role"]
