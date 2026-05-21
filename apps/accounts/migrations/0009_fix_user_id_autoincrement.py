# Migration to fix accounts_user.id AUTO_INCREMENT (MySQL)
# Run this if id values are not auto-incrementing or you see NULL ids.

from django.db import migrations


def fix_user_id_autoincrement(apps, schema_editor):
    """Ensure id column has AUTO_INCREMENT and remove any NULL id rows."""
    if schema_editor.connection.vendor != "mysql":
        return
    with schema_editor.connection.cursor() as cursor:
        # Remove invalid rows with NULL id
        cursor.execute("DELETE FROM accounts_user WHERE id IS NULL")
        # Ensure id is BIGINT NOT NULL AUTO_INCREMENT (Django BigAutoField)
        cursor.execute(
            "ALTER TABLE accounts_user "
            "MODIFY COLUMN id BIGINT NOT NULL AUTO_INCREMENT"
        )


def noop_reverse(apps, schema_editor):
    """No reversible change for schema fix."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0008_company_pricing_plan_company_subscription_period_end"),
    ]

    operations = [
        migrations.RunPython(fix_user_id_autoincrement, noop_reverse),
    ]
