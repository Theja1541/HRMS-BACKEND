from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator

class User(AbstractUser):

    ROLE_CHOICES = (
        ("SUPER_ADMIN", "Super Admin"),
        ("ADMIN", "Admin"),
        ("HR", "HR"),
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
    failed_attempts = models.IntegerField(default=0)
    is_locked = models.BooleanField(default=False, db_index=True)
    locked_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.username} ({self.role})"
    # from teja