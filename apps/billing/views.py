from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.accounts.permissions import IsSuperAdmin
from apps.accounts.models import Company
from .models import PricingPlan, Payment, Invoice
from .serializers import (
    PricingPlanSerializer,
    PaymentSerializer,
    InvoiceSerializer,
)


# ==================== PRICING PLANS ====================

@api_view(["GET", "POST"])
@permission_classes([IsSuperAdmin])
def pricing_plan_list_create(request):
    if request.method == "GET":
        qs = PricingPlan.objects.all().order_by("price_monthly")
        serializer = PricingPlanSerializer(qs, many=True)
        return Response(serializer.data)
    # POST
    serializer = PricingPlanSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "PATCH", "PUT", "DELETE"])
@permission_classes([IsSuperAdmin])
def pricing_plan_detail(request, plan_id):
    plan = PricingPlan.objects.filter(id=plan_id).first()
    if not plan:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
    if request.method == "GET":
        serializer = PricingPlanSerializer(plan)
        return Response(serializer.data)
    if request.method == "DELETE":
        plan.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    # PATCH / PUT
    serializer = PricingPlanSerializer(plan, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ==================== ASSIGN PLAN TO COMPANY ====================

@api_view(["POST"])
@permission_classes([IsSuperAdmin])
def assign_plan_to_company(request, company_id):
    company = Company.objects.filter(id=company_id).first()
    if not company:
        return Response({"detail": "Company not found."}, status=status.HTTP_404_NOT_FOUND)
    pricing_plan_id = request.data.get("pricing_plan_id")
    period_end = request.data.get("subscription_period_end")
    if not pricing_plan_id:
        return Response(
            {"pricing_plan_id": ["This field is required."]},
            status=status.HTTP_400_BAD_REQUEST,
        )
    plan = PricingPlan.objects.filter(id=pricing_plan_id, is_active=True).first()
    if not plan:
        return Response(
            {"detail": "Pricing plan not found or inactive."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    company.pricing_plan = plan
    if period_end:
        company.subscription_period_end = period_end
    company.save(update_fields=["pricing_plan", "subscription_period_end"])
    from apps.accounts.serializers import CompanySerializer
    return Response(CompanySerializer(company).data)


# ==================== PAYMENTS ====================

@api_view(["GET", "POST"])
@permission_classes([IsSuperAdmin])
def payment_list_create(request):
    if request.method == "GET":
        qs = Payment.objects.select_related("company", "pricing_plan").order_by(
            "-created_at"
        )
        company_id = request.query_params.get("company_id")
        if company_id:
            qs = qs.filter(company_id=company_id)
        serializer = PaymentSerializer(qs, many=True)
        return Response(serializer.data)
    # POST
    serializer = PaymentSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "PATCH"])
@permission_classes([IsSuperAdmin])
def payment_detail(request, payment_id):
    payment = Payment.objects.filter(id=payment_id).select_related("company", "pricing_plan").first()
    if not payment:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
    if request.method == "GET":
        serializer = PaymentSerializer(payment)
        return Response(serializer.data)
    serializer = PaymentSerializer(payment, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ==================== INVOICES ====================

@api_view(["GET", "POST"])
@permission_classes([IsSuperAdmin])
def invoice_list_create(request):
    if request.method == "GET":
        qs = Invoice.objects.select_related("company", "payment").order_by("-issued_at")
        company_id = request.query_params.get("company_id")
        if company_id:
            qs = qs.filter(company_id=company_id)
        serializer = InvoiceSerializer(qs, many=True)
        return Response(serializer.data)
    # POST
    serializer = InvoiceSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "PATCH"])
@permission_classes([IsSuperAdmin])
def invoice_detail(request, invoice_id):
    invoice = Invoice.objects.filter(id=invoice_id).select_related("company", "payment").first()
    if not invoice:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
    if request.method == "GET":
        serializer = InvoiceSerializer(invoice)
        return Response(serializer.data)
    serializer = InvoiceSerializer(invoice, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ==================== SUBSCRIPTION EXPIRY ALERTS ====================

@api_view(["GET"])
@permission_classes([IsSuperAdmin])
def subscription_alerts(request):
    """Companies with subscription_period_end in the past or within next N days."""
    today = timezone.now().date()
    days_ahead = int(request.query_params.get("days", 30))
    from datetime import timedelta
    threshold = today + timedelta(days=days_ahead)
    qs = (
        Company.objects.filter(
            is_active=True,
            subscription_period_end__isnull=False,
        )
        .filter(
            Q(subscription_period_end__lt=today)
            | Q(subscription_period_end__lte=threshold)
        )
        .select_related("pricing_plan")
        .order_by("subscription_period_end")
    )
    alerts = []
    for c in qs:
        expired = c.subscription_period_end < today
        alerts.append({
            "company_id": c.id,
            "company_name": c.name,
            "company_code": c.company_code,
            "plan_name": c.pricing_plan.name if c.pricing_plan else None,
            "subscription_period_end": c.subscription_period_end.isoformat() if c.subscription_period_end else None,
            "expired": expired,
            "days_until_expiry": (c.subscription_period_end - today).days if c.subscription_period_end else None,
        })
    return Response({"alerts": alerts})
