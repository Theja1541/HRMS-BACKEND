import logging
import json
from decimal import Decimal
from django.utils import timezone
from apps.billing.models import RazorpayWebhookLog, PaymentTransaction, CompanySubscription, SubscriptionPlan
from apps.accounts.models import Company
from apps.billing.services.subscription_service import SubscriptionService
from apps.billing.services.invoice_service import InvoiceService
from apps.billing.services.email_service import EmailService

logger = logging.getLogger(__name__)

class WebhookService:
    """Processes incoming verified Razorpay webhook events to synchronize platform state."""

    def __init__(self):
        self.sub_service = SubscriptionService()
        self.inv_service = InvoiceService()

    def process_webhook_event(self, event_type, payload, signature):
        """
        Main entry point for processing webhooks.
        Logs the raw event and prevents duplicate executions.
        """
        event_id = payload.get("id")
        log_qs = RazorpayWebhookLog.objects.filter(payload__id=event_id)
        if log_qs.exists() and log_qs.first().status == "processed":
            logger.info(f"Razorpay Webhook Event {event_id} already successfully processed. Skipping.")
            return True

        webhook_log = RazorpayWebhookLog.objects.create(
            event_type=event_type,
            payload=payload,
            signature=signature,
            status="processing"
        )

        try:
            success = False
            
            # Dispatch events
            if event_type in ["order.paid", "payment.captured"]:
                success = self._handle_payment_success(payload)
            elif event_type == "payment.failed":
                success = self._handle_payment_failure(payload)
            elif event_type in ["subscription.activated", "subscription.completed"]:
                success = self._handle_subscription_activated(payload)
            elif event_type == "subscription.charged":
                success = self._handle_subscription_charged(payload)
            elif event_type in ["subscription.cancelled", "subscription.halted"]:
                success = self._handle_subscription_cancelled(payload)
            elif event_type == "refund.processed":
                success = self._handle_refund_processed(payload)
            else:
                logger.info(f"Unhandled Razorpay Webhook Event: {event_type}")
                success = True  # Acknowledge unhandled event to avoid retry loops

            webhook_log.status = "processed" if success else "failed"
            webhook_log.save(update_fields=["status"])
            return success

        except Exception as e:
            logger.error(f"Error processing Webhook Event {event_id}: {str(e)}")
            webhook_log.status = "error"
            webhook_log.save(update_fields=["status"])
            return False

    def _handle_payment_success(self, payload):
        """Handle order.paid or payment.captured event."""
        payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
        order_id = payment_entity.get("order_id")
        payment_id = payment_entity.get("id")
        payment_method = payment_entity.get("method")
        raw_response = payload

        if not order_id:
            logger.warning("No order_id found in payment entity. Cannot process.")
            return False

        transaction = PaymentTransaction.objects.filter(razorpay_order_id=order_id).first()
        if not transaction:
            logger.warning(f"PaymentTransaction with order_id {order_id} not found in DB.")
            return False

        if transaction.payment_status == PaymentTransaction.STATUS_COMPLETED:
            logger.info(f"Transaction for order {order_id} already marked COMPLETED.")
            return True

        # Update PaymentTransaction parameters
        transaction.razorpay_payment_id = payment_id
        transaction.razorpay_signature = "webhook_verified"
        transaction.payment_method = payment_method
        transaction.payment_status = PaymentTransaction.STATUS_COMPLETED
        transaction.paid_at = timezone.now()
        transaction.raw_response_json = raw_response
        transaction.save()

        # Resolve plan and billing cycle details
        subscription = transaction.subscription
        if not subscription:
            company = transaction.company
            plan = SubscriptionPlan.objects.filter(slug="starter").first() or SubscriptionPlan.objects.first()
            billing_cycle = "monthly"
            
            # Activate subscription
            subscription = self.sub_service.activate_or_renew_subscription(
                company=company,
                plan=plan,
                billing_cycle=billing_cycle
            )
            transaction.subscription = subscription
            transaction.save(update_fields=["subscription"])
        else:
            self.sub_service.activate_or_renew_subscription(
                company=subscription.company,
                plan=subscription.subscription_plan,
                billing_cycle=subscription.billing_cycle
            )

        # Generate the GST Invoice PDF
        self.inv_service.create_gst_invoice(transaction)
        
        # Email invoice to admin
        try:
            email_service = EmailService()
            email_service.send_subscription_invoice_email(transaction)
        except Exception as mail_err:
            logger.error(f"Email delivery from webhook failed: {str(mail_err)}")
            
        return True

    def _handle_payment_failure(self, payload):
        """Handle payment.failed event."""
        payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
        order_id = payment_entity.get("order_id") or payment_entity.get("subscription_id")
        failure_reason = payment_entity.get("error_description", "Unknown failure reason")

        if not order_id:
            return False

        transaction = PaymentTransaction.objects.filter(razorpay_order_id=order_id).first()
        if transaction:
            transaction.payment_status = PaymentTransaction.STATUS_FAILED
            transaction.failure_reason = failure_reason
            transaction.raw_response_json = payload
            transaction.save()
            logger.info(f"Transaction for order {order_id} successfully marked as FAILED via Webhook.")
            
            if transaction.subscription:
                sub = transaction.subscription
                sub.payment_status = "failed"
                sub.is_active = False
                sub.save(update_fields=["payment_status", "is_active"])
            return True

        return False

    def _handle_subscription_activated(self, payload):
        """Handle subscription.activated or subscription.completed events."""
        sub_entity = payload.get("payload", {}).get("subscription", {}).get("entity", {})
        rzp_sub_id = sub_entity.get("id")

        if not rzp_sub_id:
            return False

        subscription = CompanySubscription.objects.filter(razorpay_subscription_id=rzp_sub_id).first()
        if subscription:
            self.sub_service.activate_or_renew_subscription(
                company=subscription.company,
                plan=subscription.subscription_plan,
                billing_cycle=subscription.billing_cycle
            )
            subscription.payment_status = "paid"
            subscription.is_active = True
            subscription.save(update_fields=["payment_status", "is_active"])
            logger.info(f"Subscription {rzp_sub_id} activated via Webhook successfully.")
            return True
        return False

    def _handle_subscription_charged(self, payload):
        """Handle subscription.charged event (recurring billing)."""
        sub_entity = payload.get("payload", {}).get("subscription", {}).get("entity", {})
        rzp_sub_id = sub_entity.get("id")
        payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
        payment_id = payment_entity.get("id")

        if not rzp_sub_id:
            return False

        subscription = CompanySubscription.objects.filter(razorpay_subscription_id=rzp_sub_id).first()
        if subscription:
            company = subscription.company
            plan = subscription.subscription_plan
            billing_cycle = subscription.billing_cycle

            self.sub_service.activate_or_renew_subscription(
                company=company,
                plan=plan,
                billing_cycle=billing_cycle
            )

            # Record a completed PaymentTransaction
            base_amount = plan.yearly_price if billing_cycle == "yearly" else plan.monthly_price
            gst_amount = (base_amount * plan.gst_percentage) / Decimal("100.00")
            total_amount = base_amount + gst_amount

            transaction = PaymentTransaction.objects.create(
                company=company,
                subscription=subscription,
                razorpay_order_id=payment_entity.get("order_id") or rzp_sub_id,
                razorpay_payment_id=payment_id,
                razorpay_signature="webhook_recurring",
                amount=base_amount,
                gst_amount=gst_amount,
                total_amount=total_amount,
                currency="INR",
                payment_method=payment_entity.get("method") or "recurring",
                payment_status=PaymentTransaction.STATUS_COMPLETED,
                paid_at=timezone.now(),
                raw_response_json=payload
            )

            # Generate invoice PDF
            invoice = self.inv_service.create_gst_invoice(transaction)

            # Email invoice to admin
            try:
                email_service = EmailService()
                email_service.send_subscription_invoice_email(transaction)
            except Exception as mail_err:
                logger.error(f"Webhook subscription charged email failed: {str(mail_err)}")

            logger.info(f"Extended Subscription {rzp_sub_id} for company {company.name} and generated invoice via recurring charge.")
            return True
        return False

    def _handle_subscription_cancelled(self, payload):
        """Handle subscription.cancelled or subscription.halted."""
        sub_entity = payload.get("payload", {}).get("subscription", {}).get("entity", {})
        rzp_sub_id = sub_entity.get("id")

        if not rzp_sub_id:
            return False

        subscription = CompanySubscription.objects.filter(razorpay_subscription_id=rzp_sub_id).first()
        if subscription:
            subscription.is_active = False
            subscription.payment_status = "cancelled"
            subscription.save(update_fields=["is_active", "payment_status"])
            
            # Lockout company
            company = subscription.company
            company.billing_action_stopped = True
            company.save(update_fields=["billing_action_stopped"])
            
            logger.info(f"Subscription {rzp_sub_id} cancelled and company locked out.")
            return True
        return False

    def _handle_refund_processed(self, payload):
        """Handle refund.processed webhook event."""
        payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
        order_id = payment_entity.get("order_id")

        if not order_id:
            return False

        transaction = PaymentTransaction.objects.filter(razorpay_order_id=order_id).first()
        if transaction:
            transaction.payment_status = "refunded"
            transaction.save(update_fields=["payment_status"])

            if transaction.subscription:
                sub = transaction.subscription
                sub.is_active = False
                sub.payment_status = "refunded"
                sub.save(update_fields=["is_active", "payment_status"])

                # Stop billing/lock company
                company = transaction.company
                company.billing_action_stopped = True
                company.save(update_fields=["billing_action_stopped"])

            logger.info(f"Transaction for order {order_id} refunded successfully.")
            return True
        return False
