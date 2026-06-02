from django.core.management.base import BaseCommand
from apps.billing.models import SubscriptionPlan
from decimal import Decimal

class Command(BaseCommand):
    help = "Seeds standard SaaS subscription plans: Starter, Professional, and Enterprise"

    def handle(self, *args, **options):
        plans_data = [
            {
                "name": "Starter Plan",
                "slug": "starter",
                "description": "Perfect for small companies just getting started. Includes core employee tracking, holidays, attendance, and leave management.",
                "monthly_price": Decimal("1999.00"),
                "yearly_price": Decimal("19999.00"),
                "gst_percentage": Decimal("18.00"),
                "employee_limit": 15,
                "features_json": {
                    "attendance": True,
                    "leave": True,
                    "holidays": True,
                    "notifications": True,
                    "payroll": False,
                    "assets": False,
                    "daybook": False,
                    "support": False,
                    "billing": True,
                },
                "is_active": True,
            },
            {
                "name": "Professional Plan",
                "slug": "professional",
                "description": "Ideal for mid-sized organizations. Unlocks robust Payroll processing, Support ticketing, and larger staff limits.",
                "monthly_price": Decimal("4999.00"),
                "yearly_price": Decimal("49999.00"),
                "gst_percentage": Decimal("18.00"),
                "employee_limit": 50,
                "features_json": {
                    "attendance": True,
                    "leave": True,
                    "holidays": True,
                    "notifications": True,
                    "payroll": True,
                    "assets": False,
                    "daybook": False,
                    "support": True,
                    "billing": True,
                },
                "is_active": True,
            },
            {
                "name": "Enterprise Plan",
                "slug": "enterprise",
                "description": "Unlimited potential for scaling enterprises. Complete access to Daybook Finance, Asset management, and infinite employees.",
                "monthly_price": Decimal("9999.00"),
                "yearly_price": Decimal("99999.00"),
                "gst_percentage": Decimal("18.00"),
                "employee_limit": None,
                "features_json": {
                    "attendance": True,
                    "leave": True,
                    "holidays": True,
                    "notifications": True,
                    "payroll": True,
                    "assets": True,
                    "daybook": True,
                    "support": True,
                    "billing": True,
                },
                "is_active": True,
            },
        ]

        for p_data in plans_data:
            plan, created = SubscriptionPlan.objects.update_or_create(
                slug=p_data["slug"],
                defaults=p_data,
            )
            status = "Created" if created else "Updated"
            self.stdout.write(self.style.SUCCESS(f"{status} plan: {plan.name}"))

        self.stdout.write(self.style.SUCCESS("All subscription plans seeded successfully!"))
