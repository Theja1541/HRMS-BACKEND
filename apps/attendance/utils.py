from apps.payroll.models import PayrollMonth

def is_payroll_closed(year, month):
    return PayrollMonth.objects.filter(
        year=year,
        month=month,
        status="CLOSED"
    ).exists()