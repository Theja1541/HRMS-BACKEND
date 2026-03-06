from django.utils import timezone
from django.db import transaction
from decimal import Decimal
from apps.leaves.models import LeaveType, LeaveBalance, LeaveAccrualLog
from apps.employees.models import Employee


@transaction.atomic
def run_earned_leave_accrual():

    today = timezone.now().date()
    year = today.year
    month = today.month

    try:
        earned_leave = LeaveType.objects.get(name="Earned Leave", is_active=True)
    except LeaveType.DoesNotExist:
        return "Earned Leave not configured"

    monthly_credit = Decimal(earned_leave.annual_quota) / Decimal(12)

    employees = Employee.objects.filter(is_active=True)

    for employee in employees:

        # Prevent duplicate accrual in same month
        already_credited = LeaveAccrualLog.objects.filter(
            employee=employee,
            leave_type=earned_leave,
            year=year,
            month=month
        ).exists()

        if already_credited:
            continue

        balance, _ = LeaveBalance.objects.select_for_update().get_or_create(
            employee=employee,
            leave_type=earned_leave,
            year=year,
            defaults={
                "total_allocated": 0,
                "used": 0,
            }
        )

        if balance.total_allocated < earned_leave.annual_quota:

            balance.total_allocated += monthly_credit

            if balance.total_allocated > earned_leave.annual_quota:
                balance.total_allocated = earned_leave.annual_quota

            balance.save(update_fields=["total_allocated"])

            LeaveAccrualLog.objects.create(
                employee=employee,
                leave_type=earned_leave,
                year=year,
                month=month,
                credited_days=monthly_credit
            )

    return "Earned Leave monthly accrual completed"