# Generated manually for Super Admin security settings enforcement.

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0013_company_logo"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="password_changed_at",
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
    ]
