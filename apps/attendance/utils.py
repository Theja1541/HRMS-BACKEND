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
    Checks if a given date is a weekly off for an employee based on their work calendar.
    """
    if not employee or not hasattr(employee, 'work_calendar') or not employee.work_calendar:
        # Default fallback: Sunday is week off
        return check_date.weekday() == 6
    
    calendar = employee.work_calendar
    
    # Check regular weekend days (0=Monday... 6=Sunday)
    if check_date.weekday() in calendar.weekend_days:
        return True
        
    # Check alternate Saturdays
    if check_date.weekday() == 5:
        # 5 is Saturday
        week_number = (check_date.day - 1) // 7 + 1
        if calendar.second_saturday_off and week_number == 2:
            return True
        if calendar.fourth_saturday_off and week_number == 4:
            return True
            
    return False