"""
Create an Admin user (role=ADMIN) for a company. Optional: also make them Django staff/superuser.

Usage:
  python manage.py create_admin --email admin@company.com --password YourPassword --company-id 1
  python manage.py create_admin --email admin@company.com --password YourPassword  # no company (company_id optional)
  python manage.py create_admin  # interactive prompts
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


def get_company_model():
    from apps.accounts.models import Company
    return Company


class Command(BaseCommand):
    help = "Create an Admin user (role=ADMIN) for the HRMS app. Optionally link to a company."

    def add_arguments(self, parser):
        parser.add_argument("--email", type=str, help="Admin email (used as username).")
        parser.add_argument("--password", type=str, help="Admin password.")
        parser.add_argument(
            "--company-id",
            type=int,
            default=None,
            help="Company ID to assign this admin to (optional).",
        )
        parser.add_argument(
            "--superuser",
            action="store_true",
            help="Also set is_superuser and is_staff (Django admin access).",
        )

    def handle(self, *args, **options):
        email = options.get("email") or input("Admin email: ").strip()
        password = options.get("password")
        company_id = options.get("company_id")
        make_superuser = options.get("superuser", False)

        if not email:
            self.stderr.write(self.style.ERROR("Email is required."))
            return

        if User.objects.filter(email=email).exists():
            self.stderr.write(self.style.ERROR(f"User with email '{email}' already exists."))
            return

        if not password:
            import getpass
            password = getpass.getpass("Admin password: ")
            password2 = getpass.getpass("Confirm password: ")
            if password != password2:
                self.stderr.write(self.style.ERROR("Passwords do not match."))
                return
            if len(password) < 8:
                self.stderr.write(self.style.ERROR("Password must be at least 8 characters."))
                return

        company = None
        if company_id is not None:
            Company = get_company_model()
            try:
                company = Company.objects.get(pk=company_id)
            except Company.DoesNotExist:
                self.stderr.write(
                    self.style.ERROR(f"Company with id={company_id} not found.")
                )
                return

        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            role="ADMIN",
            company=company,
            must_change_password=False,
            is_superuser=make_superuser,
            is_staff=make_superuser,
        )
        role_note = " (Django superuser + staff)" if make_superuser else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"Admin created: {user.email} (role={user.role}){role_note}. "
                f"Company: {company or 'None'}. Log in at the login page with this email and password."
            )
        )
