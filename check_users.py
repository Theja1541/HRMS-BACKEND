import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hrms_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
User = get_user_model()
for u in User.objects.all():
    print(f'User: {u.username}, Active: {u.is_active}, Role: {getattr(u, "role", "N/A")}')
