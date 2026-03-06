from django.db.models import OuterRef, Subquery, DecimalField
from django.db.models.functions import Coalesce
from decimal import Decimal

from apps.leaves.models import LeaveType, LeaveBalance


class LeaveService:

    @staticmethod
    def get_employee_balances(employee, year):

        balances_subquery = LeaveBalance.objects.filter(
            employee=employee,
            year=year,
            leave_type=OuterRef("pk")
        )

        return LeaveType.objects.filter(
            is_active=True
        ).annotate(
            total_allocated=Coalesce(
                Subquery(balances_subquery.values("total_allocated")[:1]),
                Decimal("0.00"),
                output_field=DecimalField(max_digits=6, decimal_places=2)
            ),
            used=Coalesce(
                Subquery(balances_subquery.values("used")[:1]),
                Decimal("0.00"),
                output_field=DecimalField(max_digits=6, decimal_places=2)
            ),
        )