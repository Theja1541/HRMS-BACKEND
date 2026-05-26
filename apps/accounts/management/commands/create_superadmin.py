"""
Create a SuperAdmin user (role=SUPER_ADMIN, company=null) for multi-tenant HRMS.
Usage:
  python manage.py create_superadmin --email superadmin@yourdomain.com --password YourSecurePassword
  python manage.py create_superadmin  # interactive prompts for email and password
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = "Create a SuperAdmin user (role=SUPER_ADMIN, company=null) who can manage all tenants."

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            type=str,
            help="SuperAdmin email (used as username for login).",
        )
        parser.add_argument(
            "--password",
            type=str,
            help="SuperAdmin password.",
        )

    def handle(self, *args, **options):
        import getpass

        email = options.get("email") or input("SuperAdmin email: ").strip()
        password = options.get("password")
        if not email:
            self.stderr.write(self.style.ERROR("Email is required."))
            return

        existing = User.objects.filter(email=email).first()
        if existing:
            # Upgrade existing user to Super Admin
            if not password:
                password = getpass.getpass("New SuperAdmin password (or press Enter to keep current): ")
                if password:
                    password2 = getpass.getpass("Confirm password: ")
                    if password != password2:
                        self.stderr.write(self.style.ERROR("Passwords do not match."))
                        return
                    if len(password) < 8:
                        self.stderr.write(self.style.ERROR("Password must be at least 8 characters."))
                        return
            existing.role = "SUPER_ADMIN"
            existing.company = None
            existing.is_superuser = True
            existing.is_staff = True
            existing.must_change_password = False
            existing.is_locked = False
            existing.failed_attempts = 0
            existing.locked_at = None
            if password:
                existing.set_password(password)
            existing.save()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Existing user upgraded to SuperAdmin: {existing.email}. You can log in with this email and password."
                )
            )
            return

        if not password:
            password = getpass.getpass("SuperAdmin password: ")
            password2 = getpass.getpass("Confirm password: ")
            if password != password2:
                self.stderr.write(self.style.ERROR("Passwords do not match."))
                return
            if len(password) < 8:
                self.stderr.write(self.style.ERROR("Password must be at least 8 characters."))
                return

        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            role="SUPER_ADMIN",
            company=None,
            must_change_password=False,
            is_superuser=True,
            is_staff=True,
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"SuperAdmin created: {user.email} (role={user.role}). You can log in at the login page with this email and password."
            )
        )
