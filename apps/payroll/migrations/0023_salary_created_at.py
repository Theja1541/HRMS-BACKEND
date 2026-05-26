import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payroll", "0022_payslip_bank_reference_payslip_paid_date_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="salary",
            name="created_at",
            field=models.DateTimeField(
                auto_now_add=True,
                default=django.utils.timezone.now,
            ),
            preserve_default=False,
        ),
    ]
