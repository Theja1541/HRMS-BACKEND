from apps.payroll.models import PayrollMonth
from apps.holidays.models import Holiday

def is_payroll_closed(year, month):
    return PayrollMonth.objects.filter(
        year=year,
        month=month,
        status="CLOSED"
    ).exists()

def is_holiday(check_date, company=None, state=None):
    """
    Checks if a given date is a holiday.
    Supports checking by company and state if provided.
    """
    qs = Holiday.objects.filter(
        from_date__lte=check_date,
        to_date__gte=check_date,
        is_active=True
    )
    if company:
        qs = qs.filter(company=company)
    if state:
        qs = qs.filter(state=state)
    
    holiday = qs.first()
    if holiday:
        return True, holiday
    return False, None

def is_week_off(check_date, employee):
    """
    Checks if a given date is a weekly off for an employee.
    """
    # Default: Sunday is week off
    return check_date.weekday() == 6