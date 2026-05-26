# Fix AUTO_INCREMENT for all project tables (MySQL).
# - Ensures every table's primary key has AUTO_INCREMENT.
# - Removes any rows with NULL primary key.
# - Resets AUTO_INCREMENT to max(id)+1 so next inserts get sequential IDs after deletes.

from django.db import migrations, models


def fix_all_autoincrement(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        return

    from django.db import connection

    with connection.cursor() as cursor:
        for model in apps.get_models():
            if not model._meta.managed or model._meta.abstract:
                continue
            pk = model._meta.pk
            if pk is None or not isinstance(pk, (models.AutoField, models.BigAutoField)):
                continue
            if not getattr(pk, "column", None):
                continue
            table = model._meta.db_table
            col = pk.column
            # MySQL type for AutoField -> INT, BigAutoField -> BIGINT
            sql_type = "BIGINT" if isinstance(pk, models.BigAutoField) else "INT"

            # Quote identifiers (MySQL uses backticks)
            q_table = connection.ops.quote_name(table)
            q_col = connection.ops.quote_name(col)

            try:
                # 1. Remove invalid rows with NULL primary key
                cursor.execute(
                    f"DELETE FROM {q_table} WHERE {q_col} IS NULL"
                )
                # 2. Ensure column is NOT NULL AUTO_INCREMENT
                cursor.execute(
                    f"ALTER TABLE {q_table} MODIFY COLUMN {q_col} {sql_type} NOT NULL AUTO_INCREMENT"
                )
                # 3. Set next AUTO_INCREMENT to max(id)+1 so IDs stay in order after deletes
                cursor.execute(
                    f"SELECT COALESCE(MAX({q_col}), 0) + 1 FROM {q_table}"
                )
                row = cursor.fetchone()
                next_val = row[0] if row else 1
                cursor.execute(
                    f"ALTER TABLE {q_table} AUTO_INCREMENT = %s",
                    [next_val],
                )
            except Exception as e:
                # Log but continue (e.g. table might not exist in this DB)
                import logging
                logging.getLogger(__name__).warning(
                    "AUTO_INCREMENT fix skipped for %s: %s", table, e
                )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0009_fix_user_id_autoincrement"),
    ]

    operations = [
        migrations.RunPython(fix_all_autoincrement, noop_reverse),
    ]
