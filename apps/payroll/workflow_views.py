from datetime import datetime

from django.http import HttpResponse
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status

from apps.accounts.permissions import IsAdminOrHR
from .models import Payslip
from .serializers import (
    PayrollStatusItemSerializer,
    ApprovePayrollSerializer,
    MarkPayslipPaidSerializer,
)
from .services.bank_export_service import generate_bank_salary_file


def _parse_month_or_400(month_value):
    try:
        return datetime.strptime(month_value, "%Y-%m")
    except (TypeError, ValueError):
        return None


@api_view(["GET"])
@permission_classes([IsAdminOrHR])
def payroll_status(request):
    """
    GET /api/payroll/status/?month=YYYY-MM
    Returns normalized payroll rows for payment workflow.
    """
    month_value = request.query_params.get("month")
    status_filter = request.query_params.get("status", "ALL").upper()

    month_dt = _parse_month_or_400(month_value)
    if not month_dt:
        return Response({"error": "month is required in YYYY-MM format"}, status=status.HTTP_400_BAD_REQUEST)

    queryset = Payslip.objects.select_related("employee").filter(
        month__year=month_dt.year,
        month__month=month_dt.month,
        employee__is_active=True,
    )
    if status_filter != "ALL":
        queryset = queryset.filter(status=status_filter)

    rows = PayrollStatusItemSerializer(queryset, many=True).data

    # Backward-compatible shape used by existing payroll page.
    employees = []
    for row in rows:
        display_status = "NOT PAID" if row["status"] == "GENERATED" else row["status"]
        employees.append(
            {
                "employee_id": row["employee"],
                "employee_name": row["employee_name"],
                "department": row["department"],
                "account_number": row["account_number"],
                "ifsc": row["ifsc"],
                "net_pay": row["net_pay"],
                "payslip_status": display_status,
                "status": display_status,
                "payslip_id": row["id"],
                "payslip_generated": True,
            }
        )

    return Response(
        {
            "month": month_value,
            "count": len(rows),
            "results": rows,
            "employees": employees,
        }
    )


@api_view(["POST"])
@permission_classes([IsAdminOrHR])
def approve_payroll(request):
    """
    POST /api/payroll/approve/
    body: { "month": "YYYY-MM" }
    """
    serializer = ApprovePayrollSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    month_value = serializer.validated_data["month"]

    month_dt = datetime.strptime(month_value, "%Y-%m")
    queryset = Payslip.objects.filter(
        month__year=month_dt.year,
        month__month=month_dt.month,
    )

    if not queryset.exists():
        return Response({"error": "No payslips found for this month"}, status=status.HTTP_404_NOT_FOUND)

    updated = queryset.filter(status__in=["GENERATED", "NOT PAID"]).update(status="APPROVED")

    return Response(
        {
            "message": "Payroll approved successfully",
            "month": month_value,
            "updated_count": updated,
        }
    )


@api_view(["GET"])
@permission_classes([IsAdminOrHR])
def bank_export(request):
    """
    GET /api/payroll/bank-export/?bank=SBI&month=YYYY-MM&company_account=...
    Returns CSV attachment.
    """
    bank = request.query_params.get("bank", "").upper()
    month_value = request.query_params.get("month")
    company_account = request.query_params.get("company_account", "1234567890")

    month_dt = _parse_month_or_400(month_value)
    if not month_dt:
        return Response({"error": "month is required in YYYY-MM format"}, status=status.HTTP_400_BAD_REQUEST)

    if not bank:
        return Response({"error": "bank is required"}, status=status.HTTP_400_BAD_REQUEST)

    payslips = Payslip.objects.select_related("employee").filter(
        month__year=month_dt.year,
        month__month=month_dt.month,
        status="APPROVED",
        employee__is_active=True,
    )

    employees = []
    for payslip in payslips:
        emp = payslip.employee
        if not emp.account_number or not emp.ifsc:
            continue
        employees.append(
            {
                "employee_id": emp.employee_id,
                "employee_name": f"{emp.first_name} {emp.last_name}".strip(),
                "account_number": emp.account_number,
                "ifsc": emp.ifsc,
                "net_pay": payslip.net_pay,
            }
        )

    if not employees:
        return Response(
            {"error": "No approved payslips with bank details found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        filename, csv_content = generate_bank_salary_file(
            bank=bank,
            employees=employees,
            company_account=company_account,
            month=month_value,
        )
    except ValueError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    response = HttpResponse(csv_content, content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@api_view(["POST"])
@permission_classes([IsAdminOrHR])
def mark_payslip_paid(request):
    """
    POST /api/payroll/mark-paid/
    body: { "payslip_id": 1, "bank_reference": "UTR123" }
    """
    serializer = MarkPayslipPaidSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    payslip_id = serializer.validated_data["payslip_id"]
    bank_reference = serializer.validated_data.get("bank_reference")

    try:
        payslip = Payslip.objects.get(id=payslip_id)
    except Payslip.DoesNotExist:
        return Response({"error": "Payslip not found"}, status=status.HTTP_404_NOT_FOUND)

    if payslip.status != "APPROVED":
        return Response(
            {"error": "Only APPROVED payslips can be marked as PAID"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    now = timezone.now()
    payslip.status = "PAID"
    payslip.paid_on = now
    payslip.paid_date = now
    payslip.bank_reference = bank_reference or payslip.bank_reference
    payslip.save(update_fields=["status", "paid_on", "paid_date", "bank_reference"])

    return Response(
        {
            "message": "Payslip marked as PAID",
            "payslip_id": payslip.id,
            "status": payslip.status,
            "paid_date": payslip.paid_date,
            "bank_reference": payslip.bank_reference,
        }
    )
