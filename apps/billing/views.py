from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.accounts.permissions import IsSuperAdmin
from apps.accounts.models import Company
from apps.billing.models import SubscriptionPlan, CompanySubscription, PaymentTransaction, GSTInvoice
from apps.billing.serializers import (
    SubscriptionPlanSerializer,
    PaymentTransactionSerializer,
    GSTInvoiceSerializer,
)
from apps.billing.services.razorpay_service import RazorpayService
from apps.billing.services.subscription_service import SubscriptionService
from apps.billing.services.invoice_service import InvoiceService

import logging

logger = logging.getLogger(__name__)

# ==================== SUBSCRIPTION PLANS ====================

@api_view(["GET", "POST"])
@permission_classes([IsSuperAdmin])
def pricing_plan_list_create(request):
    if request.method == "GET":
        qs = SubscriptionPlan.objects.all().order_by("monthly_price")
        serializer = SubscriptionPlanSerializer(qs, many=True)
        return Response(serializer.data)
        
    # POST - Create SubscriptionPlan and automatically create Razorpay Plans
    serializer = SubscriptionPlanSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
    data = serializer.validated_data
    try:
        with transaction.atomic():
            # 1. Create SubscriptionPlan in DB first
            plan = SubscriptionPlan.objects.create(
                name=data.get("name"),
                slug=data.get("slug"),
                description=data.get("description", ""),
                monthly_price=data.get("monthly_price"),
                yearly_price=data.get("yearly_price"),
                gst_percentage=data.get("gst_percentage", 18.00),
                employee_limit=data.get("employee_limit"),
                features_json=data.get("features_json", {}),
                is_active=data.get("is_active", True)
            )

            # Calculate total pricing inclusive of GST for Razorpay
            gst_percentage = plan.gst_percentage
            monthly_total = plan.monthly_price * (1 + gst_percentage / 100)
            yearly_total = plan.yearly_price * (1 + gst_percentage / 100)

            payment_mode = request.data.get("payment_mode", "online")

            # 2. Synchronize with Razorpay if online plan
            if payment_mode == "online":
                rzp_service = RazorpayService()
                
                try:
                    rzp_monthly_plan_id = rzp_service.create_razorpay_plan(
                        name=f"{plan.name} - Monthly",
                        price_inr=monthly_total,
                        period="monthly",
                        description=plan.description or f"Monthly subscription for {plan.name}"
                    )
                    
                    rzp_yearly_plan_id = rzp_service.create_razorpay_plan(
                        name=f"{plan.name} - Yearly",
                        price_inr=yearly_total,
                        period="yearly",
                        description=plan.description or f"Yearly subscription for {plan.name}"
                    )
                    
                    # Save Razorpay Plan IDs inside our model
                    plan.razorpay_plan_id = rzp_monthly_plan_id
                    plan.razorpay_plan_yearly_id = rzp_yearly_plan_id
                    plan.save(update_fields=["razorpay_plan_id", "razorpay_plan_yearly_id"])
                    
                except Exception as rzp_error:
                    logger.error(f"Razorpay plan creation failed: {str(rzp_error)}")
                    # Database transaction will roll back automatically due to transaction.atomic()
                    raise ValueError(f"Razorpay plan synchronization failed: {str(rzp_error)}")

            return Response(SubscriptionPlanSerializer(plan).data, status=status.HTTP_201_CREATED)

    except Exception as e:
        logger.error(f"Failed to create subscription plan: {str(e)}")
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "PATCH", "PUT", "DELETE"])
@permission_classes([IsSuperAdmin])
def pricing_plan_detail(request, plan_id):
    plan = SubscriptionPlan.objects.filter(id=plan_id).first()
    if not plan:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        
    if request.method == "GET":
        serializer = SubscriptionPlanSerializer(plan)
        return Response(serializer.data)
        
    if request.method == "DELETE":
        # Protect active company subscriptions from deletion cascade
        if plan.company_subscriptions.filter(is_active=True).exists():
            return Response(
                {"detail": "Cannot delete plan that has active subscribers. Please deactivate it instead."},
                status=status.HTTP_400_BAD_REQUEST
            )
        plan.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
        
    # PATCH / PUT
    serializer = SubscriptionPlanSerializer(plan, data=request.data, partial=True)
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
        
    plan_id = request.data.get("pricing_plan_id") or request.data.get("plan_id")
    billing_cycle = request.data.get("billing_cycle", "monthly")
    
    if not plan_id:
        return Response(
            {"pricing_plan_id": ["This field is required."]},
            status=status.HTTP_400_BAD_REQUEST,
        )
        
    plan = SubscriptionPlan.objects.filter(id=plan_id, is_active=True).first()
    if not plan:
        return Response(
            {"detail": "Subscription plan not found or inactive."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        with transaction.atomic():
            # 1. Activate subscription using SubscriptionService
            sub_service = SubscriptionService()
            subscription = sub_service.activate_or_renew_subscription(
                company=company,
                plan=plan,
                billing_cycle=billing_cycle
            )
            
            # 2. Record a mock manual payment transaction in DB for auditing
            base_amount = plan.yearly_price if billing_cycle == "yearly" else plan.monthly_price
            gst_amount = (base_amount * plan.gst_percentage) / 100
            total_amount = base_amount + gst_amount
            
            payment_method = request.data.get("payment_method", "manual")

            pay_transaction = PaymentTransaction.objects.create(
                company=company,
                subscription=subscription,
                razorpay_order_id=f"man_ord_{company.company_code}_{int(timezone.now().timestamp())}",
                razorpay_payment_id=f"man_pay_{int(timezone.now().timestamp())}",
                razorpay_signature=f"manual_admin_assign_{payment_method}",
                amount=base_amount,
                gst_amount=gst_amount,
                total_amount=total_amount,
                currency="INR",
                payment_method=payment_method,
                payment_status=PaymentTransaction.STATUS_COMPLETED,
                paid_at=timezone.now(),
                failure_reason=f"Assigned by Super Admin ({payment_method})"
            )
            
            # 3. Generate a GST Invoice PDF
            inv_service = InvoiceService()
            invoice = inv_service.create_gst_invoice(pay_transaction)
            
        from apps.accounts.serializers import CompanySerializer
        return Response(CompanySerializer(company).data)
        
    except Exception as e:
        logger.error(f"Failed to manually assign subscription to company: {str(e)}")
        return Response({"detail": f"Activation failed. {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)


# ==================== PAYMENTS ====================

@api_view(["GET", "POST"])
@permission_classes([IsSuperAdmin])
def payment_list_create(request):
    if request.method == "GET":
        qs = PaymentTransaction.objects.select_related("company", "subscription__subscription_plan").order_by("-created_at")
        company_id = request.query_params.get("company_id")
        if company_id:
            qs = qs.filter(company_id=company_id)
        
        serializer = PaymentTransactionSerializer(qs, many=True)
        
        # Adaptation mapping to ensure compatibility with old dashboard frontend keys
        adapted_data = []
        for item in serializer.data:
            adapted_item = dict(item)
            adapted_item["status"] = str(item.get("payment_status", "")).upper()
            adapted_item["payment_date"] = item.get("paid_at")[:10] if item.get("paid_at") else None
            adapted_item["reference"] = item.get("razorpay_payment_id") or item.get("razorpay_order_id")
            adapted_item["company_code"] = item.get("company_name")
            adapted_data.append(adapted_item)
            
        return Response(adapted_data)
        
    # POST (Super admin records a manual cash/bank payment transaction)
    serializer = PaymentTransactionSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "PATCH"])
@permission_classes([IsSuperAdmin])
def payment_detail(request, payment_id):
    transaction = PaymentTransaction.objects.filter(id=payment_id).select_related("company", "subscription__subscription_plan").first()
    if not transaction:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        
    if request.method == "GET":
        serializer = PaymentTransactionSerializer(transaction)
        return Response(serializer.data)
        
    serializer = PaymentTransactionSerializer(transaction, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ==================== INVOICES ====================

@api_view(["GET", "POST"])
@permission_classes([IsSuperAdmin])
def invoice_list_create(request):
    if request.method == "GET":
        qs = GSTInvoice.objects.select_related("company", "payment_transaction").order_by("-issued_at")
        company_id = request.query_params.get("company_id")
        if company_id:
            qs = qs.filter(company_id=company_id)
            
        serializer = GSTInvoiceSerializer(qs, many=True)
        
        # Adaptation mapping for front-end compatibility
        adapted_data = []
        for item in serializer.data:
            adapted_item = dict(item)
            adapted_item["amount"] = item.get("total")
            adapted_item["issued_at"] = item.get("issued_at")[:10] if item.get("issued_at") else None
            adapted_item["due_date"] = item.get("issued_at")[:10] if item.get("issued_at") else None
            adapted_item["status"] = "PAID"
            adapted_item["company_code"] = item.get("company_name")
            adapted_data.append(adapted_item)
            
        return Response(adapted_data)
        
    # POST
    serializer = GSTInvoiceSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "PATCH"])
@permission_classes([IsSuperAdmin])
def invoice_detail(request, invoice_id):
    invoice = GSTInvoice.objects.filter(id=invoice_id).select_related("company", "payment_transaction").first()
    if not invoice:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        
    if request.method == "GET":
        serializer = GSTInvoiceSerializer(invoice)
        return Response(serializer.data)
        
    serializer = GSTInvoiceSerializer(invoice, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ==================== SUBSCRIPTION EXPIRY ALERTS ====================

@api_view(["GET"])
@permission_classes([IsSuperAdmin])
def subscription_alerts(request):
    """Companies with subscription end_date in the past or within next N days."""
    today = timezone.now().date()
    days_ahead = int(request.query_params.get("days", 30))
    threshold = today + timezone.timedelta(days=days_ahead)
    
    qs = (
        CompanySubscription.objects.filter(
            is_active=True,
            end_date__isnull=False,
        )
        .filter(
            Q(end_date__lt=today)
            | Q(end_date__lte=threshold)
        )
        .select_related("company", "subscription_plan")
        .order_by("end_date")
    )
    
    alerts = []
    for sub in qs:
        expired = sub.end_date < today
        alerts.append({
            "company_id": sub.company.id,
            "company_name": sub.company.name,
            "company_code": sub.company.company_code,
            "plan_name": sub.subscription_plan.name,
            "subscription_period_end": sub.end_date.isoformat() if sub.end_date else None,
            "expired": expired,
            "days_until_expiry": (sub.end_date - today).days if sub.end_date else None,
        })
    return Response({"alerts": alerts})
