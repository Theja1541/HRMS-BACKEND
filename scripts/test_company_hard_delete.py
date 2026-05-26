import os
import sys
import django
from pathlib import Path

if __name__ == '__main__':
    # Ensure workspace root is on sys.path so Django package imports resolve
    script_path = Path(__file__).resolve()
    workspace_root = str(script_path.parents[1])  # two levels up: workspace root
    if workspace_root not in sys.path:
        sys.path.insert(0, workspace_root)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hrms_backend.settings')
    django.setup()

    from django.contrib.auth import get_user_model
    from rest_framework.test import APIRequestFactory
    from apps.accounts.views import company_hard_delete
    from apps.accounts.models import Company
    import traceback

    User = get_user_model()

    if len(sys.argv) < 2:
        print('Usage: python test_company_hard_delete.py <company_id>')
        sys.exit(2)

    company_id = int(sys.argv[1])

    # Find or create a superadmin user
    user = User.objects.filter(role='SUPER_ADMIN').first()
    if not user:
        user = User.objects.create(username='__test_superadmin__', email='test@local', role='SUPER_ADMIN')
        user.set_unusable_password()
        user.save()
        print('Created temporary superadmin user:', user.id)

    factory = APIRequestFactory()
    req = factory.delete(f'/api/accounts/companies/{company_id}/hard-delete/')
    # Mark the request as authenticated as the superadmin
    from rest_framework.test import force_authenticate
    force_authenticate(req, user=user)

    try:
        resp = company_hard_delete(req, company_id)
        try:
            # DRF Response-like
            status_code = getattr(resp, 'status_code', None)
            data = getattr(resp, 'data', None)
            print('Response status:', status_code)
            print('Response data:', data)
        except Exception:
            print('Raw response:', resp)
    except Exception as exc:
        print('Exception during call:')
        traceback.print_exc()
