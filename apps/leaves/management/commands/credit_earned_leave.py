from django.core.management.base import BaseCommand
from apps.leaves.services.accrual_service import run_earned_leave_accrual


class Command(BaseCommand):
    help = "Run monthly Earned Leave accrual"

    def handle(self, *args, **kwargs):
        result = run_earned_leave_accrual()
        self.stdout.write(self.style.SUCCESS(result))