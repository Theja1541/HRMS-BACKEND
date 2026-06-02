import logging
import json
from decimal import Decimal
from django.utils import timezone
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction as db_transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated

from apps.accounts.permissions import IsCompanyAdmin, IsCompanyAdminOrHR
from apps.billing.models import SubscriptionPlan, CompanySubscription, PaymentTransaction, GSTInvoice
from apps.billing.serializers import (
    SubscriptionPlanSerializer,
    CompanySubscriptionSerializer,
    PaymentTransactionSerializer,
    GSTInvoiceSerializer,
)
from apps.billing.services.razorpay_service import RazorpayService
from apps.billing.services.subscription_service import SubscriptionService
from apps.billing.services.invoice_service import InvoiceService
from apps.billing.services.email_service import EmailService
from apps.billing.services.webhook_service import WebhookService

logger = logging.getLogger(__name__)

# ==================== API 1: GET SUBSCRIPTION PLANS ====================

@api_view(["GET"])
@permission_classes([AllowAny])
def get_subscription_plans(request):
    """
    Public API: Returns active subscription plans.
    """
    try:
        plans = SubscriptionPlan.objects.filter(is_active=True).order_by("monthly_price")
        serializer = SubscriptionPlanSerializer(plans, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Error fetching subscription plans: {str(e)}")
        return Response(
            {"detail": "Failed to fetch subscription plans."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ==================== API 2: CREATE RAZORPAY SUBSCRIPTION ====================

@api_view(["POST"])
@permission_classes([IsCompanyAdmin])
def create_razorpay_order(request):
    """
    Authenticated Company Admin only.
    Creates a recurring subscription in Razorpay and records a pending CompanySubscription.
    """
    plan_id = request.data.get("plan_id")
    billing_cycle = request.data.get("billing_cycle", "monthly")

    if not plan_id:
        return Response({"plan_id": ["This field is required."]}, status=status.HTTP_400_BAD_REQUEST)

    if billing_cycle not in ["monthly", "yearly"]:
        return Response({"billing_cycle": ["Billing cycle must be 'monthly' or 'yearly'."]}, status=status.HTTP_400_BAD_REQUEST)

    try:
        plan = SubscriptionPlan.objects.filter(id=plan_id, is_active=True).first()
        if not plan:
            return Response({"detail": "Subscription plan not found or inactive."}, status=status.HTTP_404_NOT_FOUND)

        company = request.user.company
        if not company:
            return Response({"detail": "User is not associated with any company tenant."}, status=status.HTTP_400_BAD_REQUEST)

        # 1. Fetch correct Razorpay Plan ID based on cycle
        rzp_plan_id = plan.razorpay_plan_id if billing_cycle == "monthly" else plan.razorpay_plan_yearly_id
        
        if not rzp_plan_id:
            # Fallback if plan id is not synchronized or not created yet
            logger.warning(f"Plan ID {plan.id} has no synchronized Razorpay Plan ID for {billing_cycle}.")
            # Proactively try to create it on the fly to prevent payment failures
            rzp_service = RazorpayService()
            price = plan.monthly_price if billing_cycle == "monthly" else plan.yearly_price
            gst_total = price * (1 + plan.gst_percentage / 100)
            rzp_plan_id = rzp_service.create_razorpay_plan(
                name=f"{plan.name} - {billing_cycle.capitalize()}",
                price_inr=gst_total,
                period=billing_cycle,
                description=plan.description
            )
            if billing_cycle == "monthly":
                plan.razorpay_plan_id = rzp_plan_id
            else:
                plan.razorpay_plan_yearly_id = rzp_plan_id
            plan.save()

        # 2. Call Razorpay API to create a recurring subscription
        rzp_service = RazorpayService()
        rzp_sub = rzp_service.create_razorpay_subscription(
            plan_id=rzp_plan_id,
            trial_days=0  # Set custom trial if required
        )

        rzp_sub_id = rzp_sub.get("id")

        with db_transaction.atomic():
            # 3. Create or Update pending CompanySubscription record
            subscription, created = CompanySubscription.objects.update_or_create(
                company=company,
                defaults={
                    "subscription_plan": plan,
                    "billing_cycle": billing_cycle,
                    "is_active": False,  # Not active until verified
                    "payment_status": "pending",
                    "razorpay_subscription_id": rzp_sub_id
                }
            )

            # 4. Save a pending PaymentTransaction record
            base_amount = plan.yearly_price if billing_cycle == "yearly" else plan.monthly_price
            gst_amount = (base_amount * plan.gst_percentage) / Decimal("100.00")
            total_amount = base_amount + gst_amount

            # Delete any previous pending transaction to keep history clean
            PaymentTransaction.objects.filter(company=company, payment_status=PaymentTransaction.STATUS_PENDING).delete()

            transaction = PaymentTransaction.objects.create(
                company=company,
                subscription=subscription,
                razorpay_order_id=rzp_sub_id,  # Map subscription ID as order ID for frontend compatibility
                amount=base_amount,
                gst_amount=gst_amount,
                total_amount=total_amount,
                currency="INR",
                payment_status=PaymentTransaction.STATUS_PENDING
            )

        # 5. Calculate price inclusive of GST in paise for Checkout
        total_amount_paise = int(total_amount * Decimal("100.00"))

        return Response({
            "razorpay_order_id": rzp_sub_id,  # Frontend uses options.order_id
            "razorpay_subscription_id": rzp_sub_id, # Frontend can also read subscription_id
            "amount": total_amount_paise,
            "currency": "INR",
            "razorpay_key": getattr(settings, "RAZORPAY_KEY_ID", ""),
            "company": {
                "id": company.id,
                "name": company.name,
                "company_code": company.company_code,
                "email": request.user.email,
                "phone": company.phone,
            },
            "plan": {
                "id": plan.id,
                "name": plan.name,
                "monthly_price": str(plan.monthly_price),
                "yearly_price": str(plan.yearly_price),
                "billing_cycle": billing_cycle,
                "total_price_inr": str(total_amount),
            }
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        logger.error(f"Error creating Razorpay subscription: {str(e)}")
        return Response(
            {"detail": f"Failed to initiate subscription. {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ==================== API 3: VERIFY PAYMENT ====================

@api_view(["POST"])
@permission_classes([IsCompanyAdmin])
def verify_payment(request):
    """
    Verifies Razorpay subscription signature, updates transaction, activates company subscription, and emails GST invoice.
    """
    razorpay_order_id = request.data.get("razorpay_order_id")
    razorpay_payment_id = request.data.get("razorpay_payment_id")
    razorpay_signature = request.data.get("razorpay_signature")
    plan_id = request.data.get("plan_id")
    billing_cycle = request.data.get("billing_cycle", "monthly")

    # In subscription checkout, the subscription_id is sent back as order_id or subscription_id
    razorpay_sub_id = request.data.get("razorpay_subscription_id") or razorpay_order_id

    if not all([razorpay_sub_id, razorpay_payment_id, razorpay_signature, plan_id]):
        return Response(
            {"detail": "razorpay_subscription_id (or razorpay_order_id), razorpay_payment_id, razorpay_signature, and plan_id are required."},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        company = request.user.company
        if not company:
            return Response({"detail": "User not associated with any company tenant."}, status=status.HTTP_400_BAD_REQUEST)

        # 1. Verify recurring subscription signature securely using HMAC
        rzp_service = RazorpayService()
        is_verified = rzp_service.verify_subscription_signature(
            razorpay_payment_id=razorpay_payment_id,
            razorpay_subscription_id=razorpay_sub_id,
            razorpay_signature=razorpay_signature
        )

        if not is_verified:
            # Fallback to standard signature validation to be extra safe in case of one-off payments
            is_verified = rzp_service.verify_payment_signature(
                razorpay_order_id=razorpay_order_id,
                razorpay_payment_id=razorpay_payment_id,
                razorpay_signature=razorpay_signature
            )

        if not is_verified:
            return Response({"detail": "Signature verification failed. Potential transaction tampering detected."}, status=status.HTTP_400_BAD_REQUEST)

        # 2. Check and lock transaction processing to avoid duplicate verification
        transaction = PaymentTransaction.objects.filter(razorpay_order_id=razorpay_sub_id).first()
        if not transaction:
            transaction = PaymentTransaction.objects.filter(razorpay_order_id=razorpay_order_id).first()
            
        if not transaction:
            return Response({"detail": "Payment transaction record not found."}, status=status.HTTP_404_NOT_FOUND)

        if transaction.payment_status == PaymentTransaction.STATUS_COMPLETED:
            return Response({
                "status": "success",
                "message": "Payment already verified successfully.",
                "subscription": CompanySubscriptionSerializer(transaction.subscription).data,
                "invoice_number": transaction.invoice_number
            }, status=status.HTTP_200_OK)

        # 3. Activate subscription & lift tenant suspensions
        plan = SubscriptionPlan.objects.filter(id=plan_id).first()
        if not plan:
            return Response({"detail": "Subscription plan not found."}, status=status.HTTP_404_NOT_FOUND)

        with db_transaction.atomic():
            # Update transaction status
            transaction.razorpay_payment_id = razorpay_payment_id
            transaction.razorpay_signature = razorpay_signature
            transaction.payment_status = PaymentTransaction.STATUS_COMPLETED
            transaction.paid_at = timezone.now()
            transaction.save()

            sub_service = SubscriptionService()
            subscription = sub_service.activate_or_renew_subscription(
                company=company,
                plan=plan,
                billing_cycle=billing_cycle
            )

            # Associate subscription ID
            subscription.razorpay_subscription_id = razorpay_sub_id
            subscription.save(update_fields=["razorpay_subscription_id"])

            transaction.subscription = subscription
            transaction.save(update_fields=["subscription"])

            # 4. Generate GST invoice sequential number and ReportLab PDF
            inv_service = InvoiceService()
            invoice = inv_service.create_gst_invoice(transaction)

        # 5. Email invoice PDF asynchronously (with retry fallback)
        try:
            email_service = EmailService()
            email_service.send_subscription_invoice_email(transaction)
        except Exception as mail_err:
            logger.error(f"Failed to email subscription invoice to company admin: {str(mail_err)}")

        return Response({
            "status": "success",
            "message": "Payment verified and subscription activated successfully!",
            "subscription": CompanySubscriptionSerializer(subscription).data,
            "invoice_number": invoice.invoice_number,
            "invoice_pdf_url": invoice.invoice_pdf.url if invoice.invoice_pdf else None
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error verifying payment: {str(e)}")
        return Response(
            {"detail": f"An error occurred during verification: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ==================== API 4: PAYMENT HISTORY ====================

@api_view(["GET"])
@permission_classes([IsCompanyAdmin])
def get_payment_history(request):
    """
    Returns transaction history paginated log details.
    """
    try:
        company = request.user.company
        transactions = PaymentTransaction.objects.filter(company=company).order_by("-created_at")

        # Pagination
        from django.core.paginator import Paginator
        page_number = request.query_params.get("page", 1)
        page_size = request.query_params.get("page_size", 10)
        
        paginator = Paginator(transactions, page_size)
        page_obj = paginator.get_page(page_number)

        serializer = PaymentTransactionSerializer(page_obj.object_list, many=True)

        return Response({
            "count": paginator.count,
            "total_pages": paginator.num_pages,
            "current_page": page_obj.number,
            "results": serializer.data
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error fetching payment history: {str(e)}")
        return Response(
            {"detail": "Failed to fetch payment history."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ==================== API 5: CURRENT SUBSCRIPTION ====================

@api_view(["GET"])
@permission_classes([IsCompanyAdminOrHR])
def get_current_subscription(request):
    """
    Returns current active subscription status parameters.
    """
    try:
        company = request.user.company
        if not company:
            return Response({"detail": "User not associated with any company tenant."}, status=status.HTTP_400_BAD_REQUEST)

        sub_service = SubscriptionService()
        status_data = sub_service.get_subscription_status(company)

        # Expiry Warning Banner Calculations
        warning = False
        days_rem = status_data.get("days_remaining", 0)
        if status_data.get("has_active_subscription"):
            warning = days_rem <= 30  # Warn if less than or equal to 30 days

        status_data["expiry_warning"] = warning
        status_data["company_name"] = company.name

        return Response(status_data, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error fetching subscription status: {str(e)}")
        return Response(
            {"detail": "Failed to fetch subscription status."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ==================== WEBHOOK IMPLEMENTATION ====================

@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def razorpay_webhook(request):
    """
    Listen for incoming verified Razorpay webhook events to sync system states.
    """
    payload_body = request.body
    signature = request.META.get("HTTP_X_RAZORPAY_SIGNATURE")

    if not signature:
        logger.warning("Razorpay Webhook missing X-Razorpay-Signature header.")
        return Response({"detail": "Signature missing"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Verify webhook signature securely
        rzp_service = RazorpayService()
        is_verified = rzp_service.verify_webhook_signature(
            body_bytes=payload_body,
            signature_header=signature
        )

        if not is_verified:
            logger.warning("Razorpay Webhook signature verification failed.")
            return Response({"detail": "Signature verification failed"}, status=status.HTTP_400_BAD_REQUEST)

        # Parse event payload details
        payload = json.loads(payload_body.decode("utf-8"))
        event_type = payload.get("event")

        # Process event
        web_service = WebhookService()
        success = web_service.process_webhook_event(
            event_type=event_type,
            payload=payload,
            signature=signature
        )

        if success:
            return Response({"status": "acknowledged"}, status=status.HTTP_200_OK)
        else:
            return Response({"detail": "Failed to process event"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    except Exception as e:
        logger.error(f"Error in Razorpay Webhook Handler: {str(e)}")
        return Response({"detail": f"Internal server error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
