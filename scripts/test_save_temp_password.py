import os
import sys
from pathlib import Path

workspace_root = Path(__file__).resolve().parents[1]
if str(workspace_root) not in sys.path:
    sys.path.insert(0, str(workspace_root))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hrms_backend.settings')
import django
django.setup()

from django.contrib.auth import get_user_model
from apps.accounts.services.temporary_passwords import save_temporary_password
from apps.accounts.models import TemporaryPasswordRecord

User = get_user_model()

user = User.objects.filter(username='__test_temp_pwd_user__').first()
if not user:
    user = User.objects.create(username='__test_temp_pwd_user__', email='temp@local')
    user.set_unusable_password()
    user.save()

try:
    record = save_temporary_password(user, 'TempX123!', TemporaryPasswordRecord.PURPOSE_ONBOARDING)
    print('Saved temporary password record id:', record.id)
except Exception as e:
    print('Error:', e)
    raise
