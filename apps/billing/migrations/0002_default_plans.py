from decimal import Decimal
from django.db import migrations


def create_default_plans(apps, schema_editor):
    PricingPlan = apps.get_model("billing", "PricingPlan")
    PricingPlan.objects.get_or_create(
        code="BASIC",
        defaults={
            "name": "Basic Plan",
            "description": "Up to 50 employees",
            "price_monthly": Decimal("999.00"),
            "currency": "INR",
            "max_employees": 50,
            "is_active": True,
        },
    )
    PricingPlan.objects.get_or_create(
        code="PROFESSIONAL",
        defaults={
            "name": "Professional Plan",
            "description": "Unlimited employees",
            "price_monthly": Decimal("2999.00"),
            "currency": "INR",
            "max_employees": None,
            "is_active": True,
        },
    )


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_default_plans, reverse_noop),
    ]
