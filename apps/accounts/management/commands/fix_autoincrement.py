"""
Fix AUTO_INCREMENT on all MySQL tables and reset next ID to max(id)+1.

Run after bulk deletes in Django admin (or elsewhere) so new records get
sequential IDs and no NULL ids appear.

Usage:
  python manage.py fix_autoincrement
"""
from django.core.management.base import BaseCommand
from django.db import connection, models
from django.apps import apps


class Command(BaseCommand):
    help = (
        "Fix AUTO_INCREMENT on all tables (MySQL): remove NULL PKs, "
        "ensure AUTO_INCREMENT, set next id to max(id)+1."
    )

    def handle(self, *args, **options):
        if connection.vendor != "mysql":
            self.stdout.write(
                self.style.WARNING("This command only runs on MySQL. Skipping.")
            )
            return

        fixed = 0
        with connection.cursor() as cursor:
            for model in apps.get_models():
                if not model._meta.managed or model._meta.abstract:
                    continue
                pk = model._meta.pk
                if pk is None or not isinstance(
                    pk, (models.AutoField, models.BigAutoField)
                ):
                    continue
                if not getattr(pk, "column", None):
                    continue
                table = model._meta.db_table
                col = pk.column
                sql_type = (
                    "BIGINT"
                    if isinstance(pk, models.BigAutoField)
                    else "INT"
                )
                q_table = connection.ops.quote_name(table)
                q_col = connection.ops.quote_name(col)
                try:
                    cursor.execute(
                        f"DELETE FROM {q_table} WHERE {q_col} IS NULL"
                    )
                    cursor.execute(
                        f"ALTER TABLE {q_table} MODIFY COLUMN {q_col} "
                        f"{sql_type} NOT NULL AUTO_INCREMENT"
                    )
                    cursor.execute(
                        f"SELECT COALESCE(MAX({q_col}), 0) + 1 FROM {q_table}"
                    )
                    row = cursor.fetchone()
                    next_val = row[0] if row else 1
                    cursor.execute(
                        f"ALTER TABLE {q_table} AUTO_INCREMENT = %s",
                        [next_val],
                    )
                    fixed += 1
                    self.stdout.write(f"  {table}")
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f"  Skip {table}: {e}")
                    )
        self.stdout.write(
            self.style.SUCCESS(f"Fixed AUTO_INCREMENT on {fixed} table(s).")
        )
