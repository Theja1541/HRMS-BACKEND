from celery import shared_task
from apps.leaves.services.accrual_service import credit_monthly_leaves, credit_annual_leaves


@shared_task
def credit_monthly_leaves_task():
    """
    Celery task to credit monthly accrued leaves.
    Runs on 1st of every month.
    """
    credited_count = credit_monthly_leaves()
    return f"Credited monthly leaves to {credited_count} employee-leave combinations"


@shared_task
def credit_annual_leaves_task():
    """
    Celery task to credit annual leaves.
    Runs on January 1st.
    """
    credited_count = credit_annual_leaves()
    return f"Credited annual leaves to {credited_count} employee-leave combinations"
