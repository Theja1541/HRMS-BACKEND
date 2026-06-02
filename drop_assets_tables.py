import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hrms_backend.settings')
django.setup()

from django.db import connection

def drop_tables():
    tables_to_drop = [
        'assets_assetreturnrequest',
        'assets_asset_history',  # Not sure if there was an m2m
        'assets_asset',
        'assets_assetassignment',
        'assets_companyasset',
    ]
    with connection.cursor() as cursor:
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
        for table in tables_to_drop:
            try:
                cursor.execute(f"DROP TABLE IF EXISTS {table};")
                print(f"Dropped {table}")
            except Exception as e:
                print(f"Failed to drop {table}: {e}")
                
        cursor.execute("DELETE FROM django_migrations WHERE app = 'assets';")
        print("Deleted assets from django_migrations")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")

if __name__ == '__main__':
    drop_tables()
