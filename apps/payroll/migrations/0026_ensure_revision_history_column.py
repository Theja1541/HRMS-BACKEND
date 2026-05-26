from django.db import migrations


def forwards(apps, schema_editor):
    conn = schema_editor.connection
    with conn.cursor() as cursor:
        # Check if column exists
        cursor.execute("""
            SELECT COUNT(*)
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = 'payroll_salary'
              AND column_name = 'revision_history'
        """)
        exists = cursor.fetchone()[0]
        if exists:
            return

        # Add as nullable JSON column (some MySQL versions disallow JSON defaults)
        cursor.execute("ALTER TABLE payroll_salary ADD COLUMN revision_history JSON NULL")

        # Initialize existing rows to empty array
        cursor.execute("UPDATE payroll_salary SET revision_history = '[]' WHERE revision_history IS NULL")

        # Make column NOT NULL now that rows are initialized
        cursor.execute("ALTER TABLE payroll_salary MODIFY COLUMN revision_history JSON NOT NULL")


def backwards(apps, schema_editor):
    conn = schema_editor.connection
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT COUNT(*)
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = 'payroll_salary'
              AND column_name = 'revision_history'
        """)
        exists = cursor.fetchone()[0]
        if not exists:
            return
        cursor.execute("ALTER TABLE payroll_salary DROP COLUMN revision_history")


class Migration(migrations.Migration):

    dependencies = [
        ('payroll', '0025_remove_fullfinalsettlement_company_and_more'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
