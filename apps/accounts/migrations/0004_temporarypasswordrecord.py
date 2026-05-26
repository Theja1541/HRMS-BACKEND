from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_user_locked_at_alter_user_is_locked_alter_user_phone_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="TemporaryPasswordRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("password_hash", models.CharField(max_length=128)),
                ("purpose", models.CharField(choices=[("ONBOARDING", "Onboarding"), ("PASSWORD_RESET", "Password Reset")], db_index=True, default="ONBOARDING", max_length=20)),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("first_login_at", models.DateTimeField(blank=True, null=True)),
                ("invalidated_at", models.DateTimeField(blank=True, null=True)),
                ("email_sent_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="issued_temporary_passwords", to=settings.AUTH_USER_MODEL)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="temporary_password_record", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
