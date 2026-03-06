from datetime import date
from apps.payroll.models import Salary, SalaryRevision


def get_current_salary(employee):
    """
    Returns the latest active salary for an employee.

    Priority:
    1️⃣ Salary Revision
    2️⃣ Base Salary
    """

    today = date.today()

    # ============================================
    # 1️⃣ CHECK SALARY REVISION
    # ============================================

    revision = (
        SalaryRevision.objects
        .filter(
            employee=employee,
            effective_from__lte=today
        )
        .order_by("-effective_from")
        .first()
    )

    if revision:
        return revision

    # ============================================
    # 2️⃣ FALLBACK TO BASE SALARY
    # ============================================

    salary = Salary.objects.filter(employee=employee).first()

    if salary:
        return salary

    return None


