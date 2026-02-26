from django.db.models import Count
from django.db.models.functions import TruncMonth
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from apps.accounts.permissions import IsSuperAdmin

from apps.accounts.models import User
from apps.employees.models import Employee
from apps.leaves.models import Leave
from apps.payroll.models import Payslip


@api_view(["GET"])
@permission_classes([IsSuperAdmin])
def monthly_growth_analytics(request):

    users = (
        User.objects
        .annotate(month=TruncMonth("date_joined"))
        .values("month")
        .annotate(count=Count("id"))
        .order_by("month")
    )

    employees = (
        Employee.objects
        .annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(count=Count("id"))
        .order_by("month")
    )

    leaves = (
        Leave.objects
        .annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(count=Count("id"))
        .order_by("month")
    )

    payslips = (
        Payslip.objects
        .annotate(month=TruncMonth("generated_on"))
        .values("month")
        .annotate(count=Count("id"))
        .order_by("month")
    )

    return Response({
        "users": list(users),
        "employees": list(employees),
        "leaves": list(leaves),
        "payslips": list(payslips),
    })
