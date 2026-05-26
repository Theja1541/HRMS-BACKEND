from django.contrib import admin
from .models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = (
        "username",
        "email",
        "role",
        "is_active",
        "must_change_password",
        "is_locked",
    )
    list_filter = ("role", "is_active", "must_change_password", "is_locked")


# TemporaryPasswordRecord model removed; admin registration omitted.
